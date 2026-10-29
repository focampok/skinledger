FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DATA_DIR=/data

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

# setpriv re-execs the app as uid 10001; util-linux ships it, install only if missing.
RUN if ! command -v setpriv >/dev/null; then \
        apt-get update \
        && apt-get install -y --no-install-recommends util-linux \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh

EXPOSE 8000

# No USER line: the image starts as root so scripts/entrypoint.sh can chown the mounted
# volume, and the entrypoint re-execs uvicorn as uid 10001 before the app runs.
# Access logging is off so invite codes in query strings can never reach a log.
CMD ["/usr/local/bin/entrypoint.sh"]
