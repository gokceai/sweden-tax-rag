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
echo "=== HF env: SPACE_HOST='${SPACE_HOST}' SPACE_ID='${SPACE_ID}' SYSTEM='${SYSTEM}' ==="
if [ -n "$SPACE_HOST" ]; then
    export GRADIO_ROOT_PATH="https://$SPACE_HOST"
elif [ -n "$SPACE_ID" ]; then
    # Derive subdomain: "Owner/my-space" → "owner-my-space.hf.space"
    _AUTHOR=$(echo "$SPACE_ID" | cut -d'/' -f1 | tr '[:upper:]' '[:lower:]' | tr '_' '-')
    _REPO=$(echo "$SPACE_ID" | cut -d'/' -f2 | tr '[:upper:]' '[:lower:]' | tr '_' '-')
    export GRADIO_ROOT_PATH="https://${_AUTHOR}-${_REPO}.hf.space"
fi
echo "=== GRADIO_ROOT_PATH='${GRADIO_ROOT_PATH}' ==="

exec python src/api/main.py
