# asql development commands. Run `just --list` to see them all.

default:
    @just --list

# Install all dependencies (every extra) into .venv. --locked: a uv.lock that
# no longer matches pyproject.toml is a bug to surface, not to re-resolve.
install:
    uv sync --all-extras --locked

# Run the test suite (excludes slow and e2e tests)
test *ARGS:
    uv run --all-extras --locked pytest -q --tb=short tests -m "not slow and not e2e" {{ARGS}}

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
    echo "✅ smoke: package builds, installs, and transpiles"
