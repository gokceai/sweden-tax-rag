# Unified CPU Dockerfile — works for Hugging Face Spaces and local Docker.
# For local GPU acceleration use Dockerfile.gpu with docker-compose.gpu.yml.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default port used by HF Spaces. Override via API_PORT env var for local use.
ENV API_PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements ./requirements
COPY pyproject.toml ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/base.in -r requirements/ml.in -r requirements/ui.in

COPY src ./src
COPY example-dataset ./example-dataset
COPY scripts/entrypoint.sh ./entrypoint.sh
RUN pip install --no-cache-dir -e . && chmod +x entrypoint.sh

# HF Spaces runs containers as UID 1000.
RUN mkdir -p /data && useradd -m -u 1000 appuser && chown -R appuser /data /app
USER 1000

# Persistent storage mount point — set /data in HF Space settings.
ENV CHROMA_PERSIST_DIR=/data/chroma
ENV SQLITE_DB_PATH=/data/documents.db

EXPOSE 7860

CMD ["./entrypoint.sh"]
