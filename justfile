# asql development commands. Run `just --list` to see them all.

host := env_var_or_default("ASQL_HOST", "127.0.0.1")

default:
    @just --list

# Install all dependencies (every extra) into .venv. --locked: a uv.lock that
# no longer matches pyproject.toml is a bug to surface, not to re-resolve.
install:
    uv sync --all-extras --locked
    npm ci
    git config core.hooksPath .githooks

# Run the test suite (excludes slow and e2e tests)
test *ARGS:
    uv run --all-extras --locked pytest -q --tb=short tests -m "not slow and not e2e" {{ARGS}}

# Rust cutover crate (rust/asql-core on polyglot-sql): fmt check, clippy, parity test.
# Not part of `check`: the first build compiles polyglot-sql (~15 min).
rust-test *ARGS:
    cargo fmt --all --manifest-path rust/Cargo.toml --check
    cargo clippy --release --manifest-path rust/Cargo.toml --all-targets -- -D warnings
    cargo test --release --manifest-path rust/Cargo.toml {{ARGS}}

# Ruff lint + format check, mypy, and ESLint
lint:
    uv run --all-extras --locked ruff check .
    uv run --all-extras --locked ruff format --check .
    uv run --all-extras --locked mypy asql
    npm run lint

# Everything a PR must pass locally: lint, then the test suite
check: lint test

# Pre-review pass: the local gates, then the diff summary against BASE for a reviewer
review base="main": check
    @echo
    @echo "Changes vs {{base}}:"
    @git --no-pager diff --stat {{base}}...HEAD
    @echo
    @echo "Next: /review in Claude Code (runs /code-review and fixes confirmed findings)"

# Apply ruff fixes and formatting
fix:
    uv run --all-extras --locked ruff check --fix .
    uv run --all-extras --locked ruff format .

# Build the docs site into ./site
docs-build:
    uv run --all-extras --locked mkdocs build -d site

# Build the playground container image
docker-build tag="asql-playground:local":
    docker build -t {{tag}} .

# Build the wheel, install it into a clean venv, and transpile a query with it
smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    uv sync --all-extras --locked
    rm -rf dist .smoke-venv
    uv build --wheel
    uv venv .smoke-venv
    uv pip install --python .smoke-venv/bin/python dist/*.whl
    # -I keeps the checkout's ./asql off sys.path so the installed wheel is what runs
    .smoke-venv/bin/python -I -c '
    import asql
    sql = asql.transpile("from users where active", write="postgres")[0]
    assert sql.strip(), "asql.transpile returned empty SQL"
    print(sql)
    '
    echo "smoke: package builds, installs, and transpiles"

# Start the playground and docs together
serve playground_port="8011" docs_port="8012":
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Playground: http://{{host}}:{{playground_port}}"
    echo "Docs:       http://{{host}}:{{docs_port}}"
    trap 'kill $(jobs -p) 2>/dev/null' EXIT
    just playground {{playground_port}} &
    just docs {{docs_port}} {{playground_port}} &
    wait

# Start the playground with reload
playground port="8011":
    uv run --all-extras --locked uvicorn asql.playground.app:app --host {{host}} --port {{port}} --reload --reload-dir asql

# Serve the docs site with reload, linking to a local playground
docs port="8012" playground_port="8011":
    PLAYGROUND_URL="http://{{host}}:{{playground_port}}" uv run --all-extras --locked mkdocs serve --dev-addr {{host}}:{{port}}
