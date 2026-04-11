# Sweden Tax RAG Service

A security-first Retrieval-Augmented Generation prototype for Swedish tax law.

![status](https://img.shields.io/badge/status-prototype-orange)
![python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector-4B0082)
![SQLite](https://img.shields.io/badge/SQLite-encrypted-003B57)
![Prometheus](https://img.shields.io/badge/Prometheus-observability-E6522C)
![license](https://img.shields.io/badge/license-TBD-lightgrey)

---

## Why this exists

Most open-source RAG demos store the raw document text as metadata on the vector, which is pragmatic but leaks content to anyone who can read the collection. This project takes the opposite stance:

> **The vector store holds vectors. The encrypted store holds the text. Nothing else.**

It is a deliberate split-storage architecture with a reconciliation plane on top — a prototype for teams that want to understand what a "secure-ish" RAG layer actually looks like in code, not just on an architecture slide.

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

> Heads up: `requirements.txt` is UTF-16 LE encoded. Keep that encoding when editing or CI and Docker build will both fail loudly.

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
| Grafana | `3000` (`admin` / `admin`) |
| DCGM exporter (gpu-monitoring profile) | `9400` |

Stop the stack with `docker compose down` (or `docker compose down -v` to wipe local volumes).

> **GPU kullanımı opsiyoneldir.** Varsayılan `docker compose up -d` GPU gerektirmez.
> GPU etkinleştirmek için:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
> ```
> NVIDIA Container Toolkit kurulumunu doğrulamak için:
> ```bash
> docker info | grep -Ei 'runtimes|nvidia'
> ```

## Quick start (local, no Docker)

```bash
python -m venv .venv
source .venv/bin/activate                    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
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
| `LLM_MODEL_HOST_PATH` / `LLM_MODEL_CONTAINER_ROOT` / `LLM_MODEL_PATH_IN_CONTAINER` | Host ↔ container model path mapping for Docker. |
| `ENFORCE_ADMIN_AUTH` / `ADMIN_API_KEY` | Gate ingest/reconcile/repair endpoints with `X-Admin-Key`. |
| `RETURN_CONTEXTS_IN_RESPONSE` / `CONTEXT_RESPONSE_MODE` | Context exposure policy: `none`, `redacted` (index + char count), or `full` (admin-gated). |
| `RECONCILE_AUTORUN` / `RECONCILE_INTERVAL_SECONDS` | Background reconciliation worker. |
| `SLO_*` | Latency / error / reconcile staleness targets for alerts. |

### Deployment profiles

| Setting | Local open-source default | Shared / production |
|---|---|---|
| `ENFORCE_ADMIN_AUTH` | `false` | `true` |
| `ADMIN_API_KEY` | empty / placeholder | strong value from a secret manager |
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

Ingest a document:

```bash
curl -X POST http://localhost:8080/api/v1/ingest \
  -H "Content-Type: application/json" \
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
curl http://localhost:8080/api/v1/reconcile
curl -X POST http://localhost:8080/api/v1/reconcile/repair \
  -H "Content-Type: application/json" \
  -d '{"only_in_chroma_action":"delete","only_in_dynamo_action":"rehydrate"}'
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

## Observability

`/metrics` exposes standard HTTP metrics **plus** RAG-specific ones:

- `rag_retrieve_requests_total`, `rag_retrieve_duration_seconds`
- `rag_ingest_requests_total`, `rag_ingest_chunks_total`, `rag_ingest_duration_seconds`
- `rag_reconcile_runs_total`, `rag_reconcile_only_in_chroma`, `rag_reconcile_only_in_dynamo`, `rag_reconcile_is_consistent`
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

## Project layout

```
.
├── src/
│   ├── api/           # FastAPI app, schemas, middleware, error envelope
│   ├── core/          # config, DI factories, Fernet manager, typed exceptions
│   ├── db/            # Chroma client, SQLite repo, migration-only Dynamo client
│   ├── engine/        # RAG orchestration, LLM wrapper
│   ├── frontend/      # Gradio app (retrieval-only)
│   └── pipelines/     # Dataset ingest CLI (validate → normalize → precheck → ingest)
├── tests/             # pytest suite (unit + integration marker)
├── monitoring/        # Prometheus, Grafana, Alertmanager, runbooks
├── docker/            # Local state volumes for Chroma + SQLite
├── docker-compose.gpu.yml
├── Dockerfile.spaces
├── .github/workflows/ # CI definitions
├── docker-compose.yml
├── Dockerfile
├── AGENT.md           # Zero-memory onboarding guide for future contributors / AI agents (TR)
├── TASKS.md           # Live roadmap + reality check (TR)
└── NOTES.md           # Owner's personal interview notebook (TR) — do not edit
```

## Security model (honest version)

- ChromaDB stores embeddings and IDs. Raw text is never written there.
- SQLite stores Fernet-encrypted text keyed by `chunk_id`.
- Decryption happens only in application memory, right before the LLM call.
- The master key lives on the application host — so **this is at-rest protection, not end-to-end encryption.** If the process is compromised, the key is too. This is a deliberate tradeoff for a single-tenant prototype.
- Admin-mutating endpoints are gated by `X-Admin-Key`. `CONTEXT_RESPONSE_MODE` decides whether the API is allowed to leak decrypted text back over the wire at all.

## Roadmap

See [TASKS.md](TASKS.md) for the tracked work, but in short:

1. Decide whether Gradio stays retrieval-only or gains an admin-gated operator surface.
2. Document a production secret-management strategy end-to-end.
3. Add rate limiting in front of admin endpoints for shared deployments.

## License

No license file yet. Add one before public distribution.

---

<sub>Built as a prototype to explore split-storage RAG security patterns, not as a production-ready service. Read [AGENT.md](AGENT.md) before contributing.</sub>
