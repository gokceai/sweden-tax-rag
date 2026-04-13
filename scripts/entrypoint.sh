#!/bin/sh
# Container entrypoint: seed example data if stores are empty, then start API.
set -e

DATASET="${SEED_DATASET:-/app/example-dataset/chunks_converted.jsonl}"
MARKER="${SQLITE_DB_PATH:-/data/documents.db}.seeded"
IS_HF_SPACE=false
if [ -n "${SPACE_HOST}" ] || [ -n "${SPACE_ID}" ]; then
    IS_HF_SPACE=true
fi

DEFAULT_SEED_ON_STARTUP=true
if [ "${IS_HF_SPACE}" = "true" ]; then
    DEFAULT_SEED_ON_STARTUP=false
fi
SEED_ON_STARTUP="${SEED_ON_STARTUP:-$DEFAULT_SEED_ON_STARTUP}"

if [ "${SEED_ON_STARTUP}" = "true" ] && [ -f "$DATASET" ] && [ ! -f "$MARKER" ]; then
    echo "=== Seeding example dataset ==="
    python src/pipelines/vector_ingest/pipeline_cli.py \
        --input "$DATASET" \
        --apply \
        --reset-chroma-collection
    touch "$MARKER"
    echo "=== Seeding complete ==="
else
    echo "=== Seeding skipped (SEED_ON_STARTUP=${SEED_ON_STARTUP}) or dataset already seeded/not found ==="
fi

echo "=== HF env: SPACE_HOST='${SPACE_HOST}' SPACE_ID='${SPACE_ID}' SYSTEM='${SYSTEM}' ==="
# Keep GRADIO_ROOT_PATH untouched unless explicitly provided by the runtime.
# On HF Spaces, forcing an absolute URL here can break signed/private requests
# and lead to a blank UI.
echo "=== GRADIO_ROOT_PATH='${GRADIO_ROOT_PATH}' ==="

exec python src/api/main.py
