# The image installs the package rather than copying a source tree onto the path, so the
# container runs the same artefact that a wheel would install.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY migrations ./migrations

RUN pip install --no-cache-dir ".[postgres]" \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

# Nothing in the container needs root, and a compromised web process should not have it.
USER appuser

EXPOSE 8000

# python rather than curl, because the slim image ships no HTTP client and adding one
# just for a health check is a larger attack surface than this one line.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()"]

CMD ["uvicorn", "client_inventory.main:app", "--host", "0.0.0.0", "--port", "8000"]
