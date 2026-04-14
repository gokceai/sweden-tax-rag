---
title: Sweden Tax RAG
emoji: ⚖️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Sweden Tax RAG Service (HF Branch)

Security-first Swedish tax RAG demo optimized for Hugging Face Docker Spaces.

This branch (`hf`) ships a lean runtime:
- Gradio UI as the app surface.
- Local ChromaDB + encrypted SQLite storage.
- Script-based ingest and optional startup seeding.

## Scope

- Designed for single-container deployment (HF Spaces / local Docker).
- Split-storage RAG reference architecture.
- Prototype/security baseline, not legal advice.

## Architecture

```
User
  |
  v
Gradio App (src/frontend/app.py)
  |
  v
RAGEngine (src/engine/rag_core.py)
  |---------------------------|
  v                           v
ChromaDB vectors              SQLite encrypted chunks
(src/db/chroma_client.py)     (src/db/sqlite_document_repo.py)
  |
  v
AnswerGenerator (src/engine/llm_engine.py)
```

Retrieval flow:
1. User question enters Gradio.
2. Query embedding searches top-k `chunk_id` values in Chroma.
3. Matching encrypted chunks are read/decrypted from SQLite.
4. Context is assembled and passed to the local/gated HF model.
5. Model returns answer.

## Deploy on Hugging Face Spaces

### 1. Create Space

- Create a **Docker Space**.
- Point it to this branch (`hf`) and root `Dockerfile`.

### 2. Required secrets

- `MASTER_ENCRYPTION_KEY`
- `HUGGING_FACE_HUB_TOKEN` (required for gated models like Llama)

### 3. Common runtime vars

- `LLM_MODEL_PATH=meta-llama/Llama-3.2-1B-Instruct`
- `SEED_ON_STARTUP=false` (HF default via `entrypoint.sh`)
- `LLM_EAGER_LOAD=true`
- `LLM_USE_INT8=true`

### 4. Persistence

Use persistent storage and keep:
- `CHROMA_PERSIST_DIR=/data/chroma`
- `SQLITE_DB_PATH=/data/documents.db`

Without persistence, data is lost on restart.

## Local Run (No Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

export MASTER_ENCRYPTION_KEY="<your_fernet_key>"
python src/api/main.py
```

App listens on `http://0.0.0.0:7860` by default.

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Local Docker Run

```bash
docker build -t sweden-tax-rag:hf .
docker run --rm -p 7860:7860 \
  -e MASTER_ENCRYPTION_KEY="<your_fernet_key>" \
  -e HUGGING_FACE_HUB_TOKEN="<token_if_needed>" \
  -v "$(pwd)/docker:/data" \
  sweden-tax-rag:hf
```

## Active Configuration

Environment variables actively used by runtime code (`src/core/config.py`, `src/core/security.py`) and startup script (`scripts/entrypoint.sh`):

| Variable | Required | Purpose |
|---|---|---|
| `MASTER_ENCRYPTION_KEY` | Yes | Fernet key for encrypted chunk storage |
| `HUGGING_FACE_HUB_TOKEN` | For gated models | Auth for gated model download |
| `API_PORT` | No | Gradio port (default `7860`) |
| `LLM_MODEL_PATH` | No | HF repo id or local model path |
| `LLM_DEVICE` | No | `auto`, `cpu`, `cuda`, `mps` |
| `LLM_EAGER_LOAD` | No | Load model at startup |
| `LLM_USE_INT8` | No | Enable INT8 quantization path |
| `LLM_MAX_NEW_TOKENS` | No | Generation token cap |
| `LLM_TEMPERATURE` | No | Generation temperature |
| `EMBEDDING_MODEL` | No | SentenceTransformer model |
| `EMBEDDING_DEVICE` | No | Embedding device |
| `CHROMA_PERSIST_DIR` | No | Chroma persistence directory |
| `CHROMA_COLLECTION_NAME` | No | Chroma collection name |
| `CHROMA_DISTANCE` | No | Chroma distance metric |
| `SQLITE_DB_PATH` | No | SQLite DB path |
| `CHUNK_SIZE` | No | Chunk size for raw ingest splitting |
| `CHUNK_OVERLAP` | No | Chunk overlap for raw ingest splitting |
| `RETRIEVAL_TOP_K` | No | Final context count target |
| `RETRIEVAL_FETCH_K` | No | Candidate fetch size before filtering |
| `RETRIEVAL_MAX_DISTANCE` | No | Retrieval distance threshold |
| `MAX_CONTEXT_CHUNKS` | No | Max contexts sent to LLM |
| `MAX_CONTEXT_CHARS` | No | Max context chars sent to LLM |
| `SPACE_ID`, `SPACE_HOST` | No | HF detection for defaults |
| `SEED_ON_STARTUP` | No | Enable/disable startup seeding |
| `SEED_DATASET` | No | Seed file path override (default `/app/example-dataset/chunks.jsonl`) |

Note: `.env.example` includes additional legacy keys that are not consumed by this branch runtime.

## Data Ingest

### A) Raw documents JSONL (`text` required)

```bash
python scripts/ingest_documents_jsonl.py \
  --input documents.jsonl \
  --reset-all \
  --fail-on-skip
```

Expected row:

```json
{"doc_id":"vat_doc","title":"VAT note","text":"..."}
```

### B) Pre-chunked dataset pipeline

```bash
python src/pipelines/vector_ingest/pipeline_cli.py \
  --input example-dataset/chunks.jsonl \
  --apply \
  --reset-chroma-collection
```

Pipeline stages:
1. `dataset_validator.py`
2. `dataset_normalizer.py`
3. `ingest_precheck.py`
4. `chunk_ingest_runner.py`

## Startup Seeding Behavior

`scripts/entrypoint.sh`:
- Runs seeding once per dataset hash using marker file `/data/.seeded_<sha256>`.
- Defaults:
  - HF Space: `SEED_ON_STARTUP=false`
  - Local/non-HF: `SEED_ON_STARTUP=true`
- Launches app with `python src/api/main.py`.

## Troubleshooting (HF Blank Page)

If Space loads but UI appears blank:
1. Check browser console for `Mixed Content` or `assets/*.js 404`.
2. Ensure HTTPS rendering in Space iframe context.
3. Rebuild Space and hard refresh.

## Current Layout

```
.
├── Dockerfile
├── scripts/
│   ├── entrypoint.sh
│   └── ingest_documents_jsonl.py
├── src/
│   ├── api/main.py
│   ├── core/
│   ├── db/
│   ├── engine/
│   ├── frontend/app.py
│   ├── pipelines/vector_ingest/
│   └── services/chunk_ingest_service.py
├── example-dataset/chunks.jsonl
├── requirements/
│   ├── base.in
│   ├── ml.in
│   └── ui.in
└── .env.example
```

## Security Notes

- Raw text is intentionally not stored in Chroma metadata.
- At-rest protection is Fernet encryption in SQLite.
- If runtime host/process is compromised, secrets can still be exposed.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
