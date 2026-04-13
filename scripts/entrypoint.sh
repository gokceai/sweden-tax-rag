#!/bin/sh
# Container entrypoint: seed example data if stores are empty, then start API.
set -e

DATASET="${SEED_DATASET:-/app/example-dataset/chunks_converted.jsonl}"
MARKER="${SQLITE_DB_PATH:-/data/documents.db}.seeded"

if [ -f "$DATASET" ] && [ ! -f "$MARKER" ]; then
    echo "=== Seeding example dataset ==="
    python src/pipelines/vector_ingest/pipeline_cli.py \
        --input "$DATASET" \
        --apply \
        --reset-chroma-collection
    touch "$MARKER"
    echo "=== Seeding complete ==="
else
    echo "=== Dataset already seeded or not found, skipping ==="
fi

# Tell Gradio the public root so window.gradio_config.root is correct.
# Without this the browser JS calls http://0.0.0.0:7860 → blank page.
if [ -n "$SPACE_HOST" ]; then
    export GRADIO_ROOT_PATH="https://$SPACE_HOST"
fi

exec python src/api/main.py
