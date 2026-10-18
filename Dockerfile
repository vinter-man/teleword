FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

# The containers run with a read-only filesystem, so bytecode is compiled at build time
# (otherwise every start recompiles all dependencies). /tmp is a writable tmpfs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY teleword ./teleword
COPY assets ./assets
RUN python -m compileall -q teleword

RUN useradd --system --uid 10001 --no-create-home teleword \
    && mkdir -p /app/data \
    && chown teleword /app/data
USER teleword

CMD ["python", "-m", "teleword.bot"]
