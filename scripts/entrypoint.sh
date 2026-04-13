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

echo "=== HF env: SPACE_HOST='${SPACE_HOST}' SPACE_ID='${SPACE_ID}' SYSTEM='${SYSTEM}' ==="
# Keep GRADIO_ROOT_PATH untouched unless explicitly provided by the runtime.
# On HF Spaces, forcing an absolute URL here can break signed/private requests
# and lead to a blank UI.
echo "=== GRADIO_ROOT_PATH='${GRADIO_ROOT_PATH}' ==="

exec python src/api/main.py
