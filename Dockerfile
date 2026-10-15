# syntax=mirror.gcr.io/docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e

# The asql playground (FastAPI). Listens on $PORT (Cloud Run sets it; 8080 otherwise).

FROM mirror.gcr.io/library/python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /bin/
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dependencies first so source edits don't bust this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --extra playground --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY asql/ ./asql/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra playground --no-editable

FROM mirror.gcr.io/library/python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid 10001 --no-log-init --create-home appuser

COPY --from=builder /app/.venv /app/.venv

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, socket; s=socket.socket(); s.settimeout(3); s.connect(('localhost', int(os.environ['PORT']))); s.close()"]

CMD ["/bin/sh", "-c", "exec uvicorn asql.playground.app:app --host 0.0.0.0 --port \"$PORT\""]
