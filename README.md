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

# Sweden Tax RAG Service

A security-first Retrieval-Augmented Generation prototype for Swedish tax law.

## Positioning

**What this project is**
- A single-tenant, security-oriented RAG reference implementation.
- A public demo base that shows split storage (vectors vs encrypted text), admin-gated operations, and observability.
- A practical engineering prototype for local Docker or Hugging Face Spaces deployment.

**What this project is not**
- Not a turnkey production SaaS platform.
- Not a multi-tenant architecture with full key management isolation.
- Not a substitute for legal advice or an authoritative legal source.

![status](https://img.shields.io/badge/status-prototype-orange)
![python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector-4B0082)
![SQLite](https://img.shields.io/badge/SQLite-encrypted-003B57)
![Prometheus](https://img.shields.io/badge/Prometheus-observability-E6522C)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)

---

## Why this exists

Most open-source RAG demos store the raw document text as metadata on the vector, which is pragmatic but leaks content to anyone who can read the collection. This project takes the opposite stance:

> **The vector store holds vectors. The encrypted store holds the text. Nothing else.**

It is a deliberate split-storage architecture with a reconciliation plane on top — a prototype for teams that want to understand what a security-oriented RAG layer actually looks like in code, not just on an architecture slide.

## What's in the box

- **Split storage with field-level encryption.** ChromaDB stores `chunk_id` + embedding; SQLite stores `chunk_id` + Fernet-encrypted text. Decryption happens in application memory, right before generation.
- **Idempotent ingest.** Deterministic chunk IDs (`{source}_chunk_{i}_{sha256[:16]}`) make re-ingesting the same content a no-op instead of a duplicate.
- **Cross-store reconciliation.** Dedicated `/reconcile` and `/reconcile/repair` endpoints detect and heal drift between the two stores (`delete`, `rehydrate`, `mark_for_review`) — plus an optional background worker.
- **Pluggable admin auth + context redaction policy.** `ENFORCE_ADMIN_AUTH` gates sensitive endpoints via `X-Admin-Key`; `CONTEXT_RESPONSE_MODE` controls whether decrypted context leaks back over the wire (`none` / `redacted` / `full`).
- **Three-tier health checks** (`/health/live`, `/health/ready`, `/health/deep`) and a structured error envelope with `request_id` correlation.
- **Full Prometheus + Grafana + Alertmanager stack** with RAG-specific metrics (ingest/retrieve/reconcile/repair), SLO baselines, alert rules, and operator runbooks.
- **Thin Gradio UI** scoped to retrieval — admin surface deliberately kept off the browser.
- **CI quality gate** (lint, import smoke, unit tests, Prometheus config validation) + optional integration and compose smoke jobs on `workflow_dispatch`.

## Architecture at a glance

```
               ┌──────────────┐
               │   Client     │
               └──────┬───────┘
                      │
                      ▼
               ┌──────────────┐       ┌───────────────┐
               │  FastAPI     │──────▶│  Prometheus   │
               │  (main.py)   │       │  Grafana      │
               └──────┬───────┘       │  Alertmanager │
                      │               └───────────────┘
        ┌─────────────┴──────────────┐
        ▼                            ▼
 ┌────────────┐               ┌────────────────┐
 │  RAGEngine │               │ AnswerGenerator│
 │ rag_core.py│               │  llm_engine.py │
 └─────┬──────┘               └────────┬───────┘
       │                               │
 ┌─────┴──────┐                 ┌──────┴────────┐
 ▼            ▼                 ▼               ▼
ChromaDB   SQLite            Transformers    Local Llama
(vectors) (encrypted text)   + Torch (GPU)    weights
```

**Data flow on retrieval:** question → embed → Chroma search returns top-k `chunk_id`s → SQLite lookup → Fernet decrypt in memory → LLM generates an answer grounded strictly in the decrypted context → response (context is redacted/hidden per policy).

## Tech stack (what's actually wired up)

| Layer | Choice |
|---|---|
| API | FastAPI |
| UI | **Gradio** (retrieval-only) |
| Vector store | ChromaDB (`PersistentClient`) |
| Encrypted text store | SQLite |
| Encryption | `cryptography.Fernet` (AES-128-CBC + HMAC-SHA256) |
| Embeddings | `sentence-transformers / all-MiniLM-L6-v2` (384-dim) |
| Chunking | `langchain_text_splitters.RecursiveCharacterTextSplitter` |
| LLM runtime | Hugging Face Transformers + Torch, local Llama-compatible weights |
| Observability | Prometheus, Grafana, Alertmanager, optional NVIDIA DCGM exporter |
| CI | GitHub Actions (`ruff`, `pytest`, `promtool`) |

## Quick start (Docker)

```bash
cp .env.example .env
# Generate a Fernet key and paste it into MASTER_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up -d                              # api (CPU default)
docker compose --profile ui up -d                 # + Gradio
docker compose --profile monitoring up -d --no-build  # + Prometheus/Grafana/Alertmanager
```

Ports:

| Service | Port |
|---|---|
| FastAPI | `8080` |
| Gradio UI | `8501` |
| Prometheus | `9090` |
| Alertmanager | `9093` |
| Grafana | `3000` (uses `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`) |
| DCGM exporter (gpu-monitoring profile) | `9400` |

Stop the stack with `docker compose down` (or `docker compose down -v` to wipe local volumes).

> **GPU usage is optional.** The default `docker compose up -d` does not require a GPU.
> To enable GPU support:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
> ```
> To verify NVIDIA Container Toolkit installation:
> ```bash
> docker info | grep -Ei 'runtimes|nvidia'
> ```

## Public demo card

Use this as the single-source summary for a public GitHub/Hugging Face demo.

| Topic | Public demo guidance |
|---|---|
| Public endpoints | Intended public surface: `POST /api/v1/retrieve` (main user flow), `GET /`, `GET /health/live`, `GET /health/ready`. The Gradio UI calls only retrieval. |
| Admin endpoint policy | Keep `ENFORCE_ADMIN_AUTH=true` for public deployments. `POST /api/v1/ingest`, `GET /api/v1/reconcile`, `GET /api/v1/reconcile/last`, and `POST /api/v1/reconcile/repair` must require `X-Admin-Key`. Never expose `ADMIN_API_KEY` in frontend code or client-visible config. |
| First-run model download | If `LLM_MODEL_PATH` is a Hugging Face repo ID (default: `meta-llama/Llama-3.2-1B-Instruct`), first retrieval triggers a one-time model download. Typical cold-start is about 2-15 minutes depending on network, disk speed, and model size. |
| CPU response time (approx.) | After warm-up, short retrieval questions are typically around 3-15 seconds on a modern desktop CPU with the default 1B model. Slower CPUs, longer contexts, or higher `top_k` can increase latency. |
| Demo dataset | This repo does not ship a production legal corpus by default. For demos, ingest your own non-sensitive JSONL sample (for example via `scripts/ingest_documents_jsonl.py` or the pre-chunked pipeline) and document the data source in the Space card/README. |

## Public deployment security policy

Use this section as the baseline policy for public GitHub/Hugging Face deployments.

| Policy area | Required policy |
|---|---|
| Secrets exposure policy | Keep all secrets in environment variables/Space secrets only (`MASTER_ENCRYPTION_KEY`, `ADMIN_API_KEY`). Never hardcode or expose them in frontend code, logs, screenshots, or example curl output. |
| Admin gating | Set `ENFORCE_ADMIN_AUTH=true` and require `X-Admin-Key` for all mutating/admin routes. Keep admin operations off the public UI. |
| Ingest policy (public) | Default to ingest closed for anonymous users. If ingest must be enabled, keep it admin-only and rate-limited; never allow untrusted public uploads without additional validation and moderation controls. |
| Persistent storage implications | With persistent volumes enabled, vectors and encrypted text survive restarts. Without persistence, data resets on container/Space restart and must be re-ingested. |
| Demo-only data policy | Use only non-sensitive, redistributable demo data. Do not ingest personal, confidential, or licensed-restricted corpora into public demos. |

## Quick start (local, no Docker)

```bash
python -m venv .venv
source .venv/bin/activate                    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements/dev.in
pip install -e .

uvicorn src.api.main:app --reload --port 8080
python src/frontend/app.py                   # Gradio on :8501
```

With no container, keep `.env` values at their `localhost` defaults — `docker-compose.yml` overrides service hostnames only inside containers.

## HuggingFace Spaces deployment

1. Fork this repository.
2. In Hugging Face Spaces, create a new **Docker** Space.
3. Copy `.env.example` values into Space secrets and set `MASTER_ENCRYPTION_KEY`.
4. Use `Dockerfile.spaces` as the Space Dockerfile.
5. Enable persistent storage (`/data` mount). Without it, data resets on restart.
6. Keep `LLM_MODEL_PATH` as an HF repo ID if desired; the model downloads on first retrieval.

## Configuration that actually matters

Full list lives in [src/core/config.py](src/core/config.py). The critical ones:

| Variable | Purpose |
|---|---|
| `MASTER_ENCRYPTION_KEY` | **Required.** Valid Fernet key. Missing → app refuses to start. |
| `LLM_MODEL_PATH` | Path or HF repo ID loadable by `AutoModelForCausalLM`. |
| `EMBEDDING_MODEL` / `EMBEDDING_DEVICE` | Embedding model and runtime device (`auto`, `cpu`, `cuda`). |
| `LLM_MODEL_HOST_PATH` / `LLM_MODEL_CONTAINER_ROOT` / `LLM_MODEL_PATH_IN_CONTAINER` | Host ↔ container model path mapping for Docker. |
| `ENFORCE_ADMIN_AUTH` / `ADMIN_API_KEY` | Gate ingest/reconcile/repair endpoints with `X-Admin-Key`. |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | Monitoring profile login for Grafana. |
| `RETURN_CONTEXTS_IN_RESPONSE` / `CONTEXT_RESPONSE_MODE` | Context exposure policy: `none`, `redacted` (index + char count), or `full` (admin-gated). |
| `RECONCILE_AUTORUN` / `RECONCILE_INTERVAL_SECONDS` | Background reconciliation worker. |
| `SLO_*` | Latency / error / reconcile staleness targets for alerts. |

### Deployment profiles

| Setting | Local open-source default | Shared / production |
|---|---|---|
| `ENFORCE_ADMIN_AUTH` | `true` | `true` |
| `ADMIN_API_KEY` | strong local secret | strong value from a secret manager |
| `GRAFANA_ADMIN_PASSWORD` | non-default secret | secret manager value |
| `RETURN_CONTEXTS_IN_RESPONSE` | `false` | `false` |
| `CONTEXT_RESPONSE_MODE` | `none` | `none` or `redacted` |
| `RECONCILE_AUTORUN` | `false` | `true` |

## API surface

### Health

| Endpoint | Purpose |
|---|---|
| `GET /` | Liveness ping + service metadata |
| `GET /health/live` | Process alive |
| `GET /health/ready` | Chroma + SQLite reachable (503 otherwise) |
| `GET /health/deep` | Real query + scan probe (more expensive) |
| `GET /metrics` | Prometheus format |

### Main flow

| Endpoint | Admin-gated? |
|---|---|
| `POST /api/v1/ingest` | yes |
| `POST /api/v1/retrieve` | no (public) |
| `GET /api/v1/reconcile` | yes |
| `GET /api/v1/reconcile/last` | yes |
| `POST /api/v1/reconcile/repair` | yes |

### Error envelope

Every non-2xx response follows a stable shape so clients can triage programmatically:

```json
{
  "detail": {
    "message": "Unexpected retrieval failure.",
    "error_code": "retrieve_unexpected_error",
    "error_category": "server_error",
    "request_id": "f4a9…"
  }
}
```

`X-Request-ID` is generated by middleware (or echoed if provided), attached to every response, and emitted into structured JSON logs.

## API examples

> **Auth note:** Admin routes require `X-Admin-Key` by default (`ENFORCE_ADMIN_AUTH=true` in `.env.example`).
> For local-only experimentation, you can temporarily set `ENFORCE_ADMIN_AUTH=false`, but do not use that setting in shared/public deployments.

Ingest a document:

```bash
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: <ADMIN_API_KEY>" \
  -d '{"document_text":"VAT on hotel stays in Sweden may use a reduced rate of 12 percent.","source_name":"hotel_vat_notes.txt"}'
```

Ask a question:

```bash
curl -X POST http://localhost:8080/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"What tax rate applies to staying in a hotel?","top_k":2}'
```

Reconcile drift:

```bash
curl -H "X-Admin-Key: <ADMIN_API_KEY>" \
  http://localhost:8080/api/v1/reconcile

curl -X POST http://localhost:8080/api/v1/reconcile/repair \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: <ADMIN_API_KEY>" \
  -d '{"only_in_chroma_action":"delete","only_in_document_store_action":"rehydrate"}'
```

## Dataset ingest pipeline

For pre-chunked JSONL corpora there is a dedicated pipeline under [src/pipelines/vector_ingest/](src/pipelines/vector_ingest/):

```
pipeline_cli.py  →  dataset_validator.py
                 →  dataset_normalizer.py  (Unicode NFC + whitespace + hash refresh)
                 →  ingest_precheck.py     (dry-run collision report vs. current stores)
                 →  chunk_ingest_runner.py (idempotent SQLite + Chroma write)
```

```bash
python src/pipelines/vector_ingest/pipeline_cli.py \
  --input example-dataset/chunks.jsonl \
  --apply \
  --reset-chroma-collection
```

## Adding new data
Treat all ingest operations as admin-only by default.

### Option A: API ingest (single document)

```bash
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: <ADMIN_API_KEY>" \
  -d '{"document_text":"...","source_name":"my_source.txt"}'
```

### Option B: Raw JSONL bulk ingest (`doc_id` + `text`)

```bash
python scripts/ingest_documents_jsonl.py \
  --input documents.jsonl \
  --reset-all \
  --fail-on-skip
```

Use `--reset-all` when replacing a dataset end-to-end, so Chroma and SQLite stay in sync.

### Option C: Pre-chunked JSONL bulk ingest (`chunk_id` present)

```bash
python src/pipelines/vector_ingest/pipeline_cli.py \
  --input example-dataset/chunks.jsonl \
  --apply \
  --reset-chroma-collection
```

## Observability

`/metrics` exposes standard HTTP metrics **plus** RAG-specific ones:

- `rag_retrieve_requests_total`, `rag_retrieve_duration_seconds`
- `rag_ingest_requests_total`, `rag_ingest_chunks_total`, `rag_ingest_duration_seconds`
- `rag_reconcile_runs_total`, `rag_reconcile_only_in_chroma`, `rag_reconcile_only_in_document_store`, `rag_reconcile_is_consistent`
- `rag_repair_requests_total`, `rag_repair_duration_seconds`

Alert rules ([monitoring/prometheus/alerts.yml](monitoring/prometheus/alerts.yml)): `HighApi5xxRate`, `HighApiP95Latency`, `GpuExporterDown`.

Operator runbooks ship with the repo:
- [monitoring/runbooks/retrieve_incident_runbook.txt](monitoring/runbooks/retrieve_incident_runbook.txt)
- [monitoring/runbooks/reconcile_repair_runbook.txt](monitoring/runbooks/reconcile_repair_runbook.txt)
- [monitoring/runbooks/gpu_fallback_runbook.txt](monitoring/runbooks/gpu_fallback_runbook.txt)

## Tests

```bash
pytest -q                    # unit tests
pytest -q -m integration     # embedded Chroma + SQLite integration checks
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs:
- `ruff` lint gate (syntax/undefined-name critical rules)
- Prometheus config + rules validation via `promtool`
- Import smoke for core modules
- `pytest -m "not integration"`
- Monitoring smoke subset (`-k "metrics or health"`)
- Optional integration + compose smoke jobs on `workflow_dispatch`

## Dependency workflow

- `requirements/base.in`: core API/runtime dependencies.
- `requirements/ml.in`: model and embedding stack.
- `requirements/ui.in`: frontend dependencies.
- `requirements/dev.in`: test/lint/tooling (includes base + ml + ui).
- `requirements.txt`: runtime aggregate for backward compatibility (`-r base.in -r ml.in -r ui.in`).

## Project layout

```
.
├── src/
│   ├── api/           # FastAPI app, schemas, middleware, error envelope
│   ├── core/          # config, DI factories, Fernet manager, typed exceptions
│   ├── db/            # Chroma client, SQLite encrypted document repository
│   ├── engine/        # RAG orchestration, LLM wrapper
│   ├── frontend/      # Gradio app (retrieval-only)
│   └── pipelines/     # Dataset ingest CLI (validate → normalize → precheck → ingest)
├── scripts/           # Utility scripts (for example raw JSONL ingest)
├── tests/             # pytest suite (unit + integration marker)
├── monitoring/        # Prometheus, Grafana, Alertmanager, runbooks
├── docker/            # Local state volumes for Chroma + SQLite
├── docker-compose.gpu.yml
├── Dockerfile.spaces
├── .github/workflows/ # CI definitions
├── docker-compose.yml
└── Dockerfile
```

## Security model (honest version)

- ChromaDB stores embeddings and IDs. Raw text is never written there.
- SQLite stores Fernet-encrypted text keyed by `chunk_id`.
- Decryption happens only in application memory, right before the LLM call.
- The master key lives on the application host — so **this is at-rest protection, not end-to-end encryption.** If the process is compromised, the key is too. This is a deliberate tradeoff for a single-tenant prototype.
- Admin-mutating endpoints are gated by `X-Admin-Key`. `CONTEXT_RESPONSE_MODE` decides whether the API is allowed to leak decrypted text back over the wire at all.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).

---
<sub>Built as a prototype to explore split-storage RAG security patterns, not as a production-ready service.</sub>
