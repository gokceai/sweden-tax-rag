#!/bin/sh
# Container entrypoint: seed dataset if needed, then start API.
set -e

DATASET="${SEED_DATASET:-/app/example-dataset/chunks.jsonl}"

IS_HF_SPACE=false
if [ -n "${SPACE_HOST}" ] || [ -n "${SPACE_ID}" ]; then
    IS_HF_SPACE=true
fi

DEFAULT_SEED_ON_STARTUP=true
if [ "${IS_HF_SPACE}" = "true" ]; then
    DEFAULT_SEED_ON_STARTUP=false
fi
SEED_ON_STARTUP="${SEED_ON_STARTUP:-$DEFAULT_SEED_ON_STARTUP}"

DATASET_HASH=""
if [ -f "$DATASET" ]; then
    DATASET_HASH="$(sha256sum "$DATASET" | awk '{print $1}')"
fi
MARKER="/data/.seeded_${DATASET_HASH}"

if [ "${SEED_ON_STARTUP}" = "true" ] && [ -f "$DATASET" ] && [ -n "$DATASET_HASH" ] && [ ! -f "$MARKER" ]; then
    echo "=== Seeding dataset: $DATASET ==="
    echo "=== Dataset hash: $DATASET_HASH ==="
    python src/pipelines/vector_ingest/pipeline_cli.py \
        --input "$DATASET" \
        --apply \
        --reset-chroma-collection \
        --reset-document-store \
        --reconcile-missing
    touch "$MARKER"
    echo "=== Seeding complete ==="
else
    echo "=== Seeding skipped (SEED_ON_STARTUP=${SEED_ON_STARTUP}) or dataset already seeded/not found ==="
    echo "=== DATASET='$DATASET' HASH='$DATASET_HASH' MARKER='$MARKER' ==="
fi

echo "=== HF env: SPACE_HOST='${SPACE_HOST}' SPACE_ID='${SPACE_ID}' SYSTEM='${SYSTEM}' ==="
echo "=== GRADIO_ROOT_PATH='${GRADIO_ROOT_PATH}' ==="

exec python src/api/main.py