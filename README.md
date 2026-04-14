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

This branch (`hf`) intentionally ships a lean runtime:
- Gradio UI as the primary app surface.
- Local ChromaDB + encrypted SQLite storage.
- Script-based ingest and reconciliation prep.
- No public FastAPI endpoint surface in this branch.

## What this branch is

- A Hugging Face friendly demo branch with low operational overhead.
- A split-storage RAG reference: embeddings in Chroma, encrypted text in SQLite.
- A practical baseline for single-container deployment on Spaces.

## What this branch is not

- Not the full observability/CI heavy profile from `main`.
- Not a multi-tenant or production key-management architecture.
- Not legal advice.

## Main vs HF branch (important)

If you compare `main...hf`, the big differences are intentional.

| Area | `main` branch | `hf` branch (this README) |
|---|---|---|
| App surface | FastAPI + Gradio | Gradio launch only (`python src/api/main.py`) |
| Docker setup | Multiple compose profiles + GPU file | Single unified `Dockerfile` |
| Monitoring | Prometheus/Grafana/Alertmanager configs | Removed for Space simplicity |
| CI/tests in repo | Workflow + test suite present | Removed from this branch |
| Seed strategy | Environment/profile dependent | `entrypoint.sh` defaults `SEED_ON_STARTUP=false` on HF |

## Architecture (hf branch)

```
User (HF Space iframe)
        │
        ▼
   Gradio App
(src/frontend/app.py)
        │
        ▼
     RAGEngine
(src/engine/rag_core.py)
   ┌───────────────┴───────────────┐
   ▼                               ▼
ChromaDB (vectors)      SQLite (Fernet-encrypted text)
(src/db/chroma_client.py) (src/db/sqlite_document_repo.py)
        │
        ▼
 AnswerGenerator (Transformers + Torch)
(src/engine/llm_engine.py)
```

Retrieval flow:
1. User asks in Gradio.
2. Query embedding searches top-k `chunk_id` in Chroma.
3. Matching encrypted chunks are fetched/decrypted from SQLite.
4. Prompt is built from retrieved contexts.
5. Local/gated HF model generates the answer.

## Core capabilities in this branch

- Split storage model:
  - Chroma stores embeddings + safe metadata.
  - SQLite stores encrypted text payloads.
- Deterministic chunk IDs for idempotent ingest.
- Rollback protection during ingest if one store write fails.
- Optional startup seeding from `example-dataset/chunks.jsonl`.
- CPU-first runtime with optional INT8 quantization path.

## Hugging Face Spaces deployment

### 1. Create Space

- Create a new **Docker Space**.
- Point it to this branch (`hf`) or repo state containing this README and Dockerfile.

### 2. Build/runtime file

- Use repository root `Dockerfile` (there is no `Dockerfile.spaces` in this branch).

### 3. Space secrets (minimum)

Set these in Space Secrets:

- `MASTER_ENCRYPTION_KEY` (required)
- `HUGGING_FACE_HUB_TOKEN` (required for gated models like Llama)

Recommended runtime secrets/vars:

- `LLM_MODEL_PATH=meta-llama/Llama-3.2-1B-Instruct`
- `SEED_ON_STARTUP=false` (default behavior on HF via entrypoint)
- `LLM_EAGER_LOAD=true`
- `LLM_USE_INT8=true`

### 4. Persistent storage

Enable persistent storage and keep default paths:

- `CHROMA_PERSIST_DIR=/data/chroma`
- `SQLITE_DB_PATH=/data/documents.db`

Without persistence, vectors/documents are lost at restart.

## Local run (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements/base.in -r requirements/ml.in -r requirements/ui.in
pip install -e .

# required
export MASTER_ENCRYPTION_KEY="<your_fernet_key>"

python src/api/main.py
```

App listens on `http://0.0.0.0:7860` by default.

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Docker run (local)

```bash
docker build -t sweden-tax-rag:hf .
docker run --rm -p 7860:7860 \
  -e MASTER_ENCRYPTION_KEY="<your_fernet_key>" \
  -e HUGGING_FACE_HUB_TOKEN="<token_if_needed>" \
  -v "$(pwd)/docker:/data" \
  sweden-tax-rag:hf
```

## Configuration (actively used in this branch)

Defined in [`src/core/config.py`](src/core/config.py) and runtime launch path.

| Variable | Required | Purpose |
|---|---|---|
| `MASTER_ENCRYPTION_KEY` | Yes | Fernet key for encrypted chunk storage |
| `HUGGING_FACE_HUB_TOKEN` | For gated models | Auth for model download |
| `API_PORT` | No | Gradio listen port (default `7860`) |
| `LLM_MODEL_PATH` | No | HF repo id or local model path |
| `LLM_DEVICE` | No | `auto`, `cpu`, `cuda`, `mps` |
| `LLM_EAGER_LOAD` | No | Load model at startup |
| `LLM_USE_INT8` | No | INT8 quantization path |
| `EMBEDDING_MODEL` | No | SentenceTransformer model |
| `EMBEDDING_DEVICE` | No | Embedding device selection |
| `CHROMA_PERSIST_DIR` | No | Chroma persistent directory |
| `CHROMA_COLLECTION_NAME` | No | Chroma collection name |
| `CHROMA_DISTANCE` | No | Chroma similarity metric |
| `SQLITE_DB_PATH` | No | SQLite document store path |
| `CHUNK_SIZE` | No | Splitter chunk size |
| `CHUNK_OVERLAP` | No | Splitter overlap |
| `LLM_MAX_NEW_TOKENS` | No | Generation token cap |
| `LLM_TEMPERATURE` | No | Generation sampling temperature |
| `GRADIO_ROOT_PATH` | No | Explicit root path override if needed |
| `SEED_ON_STARTUP` | No | Enable/disable startup seed in entrypoint |

Note: `.env.example` still includes some legacy variables from `main` (admin API/monitoring fields). They are currently not consumed by `hf` runtime code.

## Data ingest options

This branch uses scripts/CLI for ingest.

### A) Raw JSONL documents (`text` required)

```bash
python scripts/ingest_documents_jsonl.py \
  --input documents.jsonl \
  --reset-all \
  --fail-on-skip
```

Expected per-line JSON:

```json
{"doc_id":"vat_doc","title":"VAT note","text":"..."}
```

### B) Pre-chunked JSONL pipeline

```bash
python src/pipelines/vector_ingest/pipeline_cli.py \
  --input example-dataset/chunks_converted.jsonl \
  --apply \
  --reset-chroma-collection
```

Pipeline order:
1. `dataset_validator.py`
2. `dataset_normalizer.py`
3. `ingest_precheck.py`
4. `chunk_ingest_runner.py`

## Hugging Face blank page troubleshooting

If the Space opens but shows a blank page:

1. Check browser console for `Mixed Content` or `assets/*.js 404`.
2. Ensure app is served over HTTPS in Space iframe context.
3. Keep `GRADIO_ROOT_PATH` empty unless explicitly required.
4. Rebuild Space and hard-refresh browser.

Non-blocking warning lines such as `Unrecognized feature: ...` in console are typically iframe permission-policy noise and not fatal by themselves.

## Current project layout

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
│   └── pipelines/vector_ingest/
├── example-dataset/chunks.jsonl
├── requirements/
│   ├── base.in
│   ├── ml.in
│   └── ui.in
└── .env.example
```

## Security notes

- Raw document text is not persisted in Chroma metadata by design.
- At-rest protection is provided by Fernet encryption in SQLite.
- If runtime process or host is compromised, secrets can be compromised too.
- Treat this as a secure prototype pattern, not a complete production security boundary.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
