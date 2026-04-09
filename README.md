# Sweden Tax RAG Service

An early-stage prototype of a secure Retrieval-Augmented Generation (RAG) service for Swedish tax content.

The project combines:

- FastAPI for the API
- Streamlit for a simple operator UI
- ChromaDB for semantic search
- DynamoDB Local for encrypted chunk storage
- `cryptography.Fernet` for encryption at rest
- Sentence Transformers for embeddings
- A local Llama-compatible model for answer generation

The intended design is straightforward:

- ChromaDB stores vectors and chunk IDs only
- DynamoDB stores the encrypted original text
- The application retrieves matching chunk IDs from ChromaDB
- The application decrypts the related text from DynamoDB
- The LLM answers using only the retrieved context

## Current Status

This repository is not production-ready yet. It already demonstrates the main data flow, but it still has important gaps:

- Infrastructure and model loading are tightly coupled to import-time side effects
- Several settings are hard-coded in code instead of being fully configuration-driven
- The repository now includes baseline `pytest` unit tests for API, engine, and security layers
- The ingest pipeline is not transactional across ChromaDB and DynamoDB
- Decrypted contexts can be hidden by default via `RETURN_CONTEXTS_IN_RESPONSE=false`

If you treat this as a prototype or architecture spike, the repository makes sense. If you treat it as a finished service, it still needs another round of engineering.

## Architecture Overview

### Data Flow

1. A client submits a document to `/api/v1/ingest`.
2. The RAG engine splits the document into chunks with `RecursiveCharacterTextSplitter`.
3. Each chunk is embedded with `all-MiniLM-L6-v2`.
4. The vector is stored in ChromaDB together with the generated `chunk_id`.
5. The original chunk text is encrypted with Fernet and stored in DynamoDB Local.
6. A user submits a question to `/api/v1/retrieve`.
7. The system searches ChromaDB for similar chunk IDs.
8. The matching encrypted chunks are fetched from DynamoDB and decrypted.
9. The combined context is inserted into the system prompt and sent to the LLM.
10. The generated answer is returned to the client.

### Main Components

- `src/api/main.py`: FastAPI routes for ingest and retrieval
- `src/api/schemas.py`: Request models
- `src/core/config.py`: Shared settings and prompts
- `src/core/security.py`: Fernet encryption manager
- `src/db/chroma_client.py`: ChromaDB access and vector operations
- `src/db/dynamo_client.py`: DynamoDB Local access and table bootstrap
- `src/db/document_repo.py`: Encrypted chunk persistence
- `src/engine/rag_core.py`: Chunking, ingest, and retrieval logic
- `src/engine/llm_engine.py`: Local LLM loading and text generation
- `src/frontend/app.py`: Streamlit user interface

## Repository Layout

```text
.
|-- docker/
|-- notebooks/
|-- src/
|   |-- api/
|   |-- core/
|   |-- db/
|   |-- engine/
|   `-- frontend/
|-- tests/
|-- .env.example
|-- docker-compose.yml
|-- requirements.txt
|-- agent.md
|-- ADVICE.md
`-- README.md
```

## Prerequisites

- Python 3.12 recommended
- Docker Desktop or another Docker runtime
- A valid Fernet key for `MASTER_ENCRYPTION_KEY`
- A local or downloadable Llama-compatible model

## Environment Configuration

Create your local environment file from `.env.example` and fill in the values:

```env
MASTER_ENCRYPTION_KEY=
LLM_MODEL_PATH=meta-llama/Llama-3.2-1B-Instruct
```

### Generate A Fernet Key

Use this command to generate a valid key:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then place the output into `MASTER_ENCRYPTION_KEY`.

### Recommended Profiles (Open-Source vs Production)

Use this as a practical baseline when publishing the project publicly (GitHub/Hugging Face):

| Setting | Open-source default (easy first run) | Production/shared deployment (recommended) |
|---|---|---|
| `ENFORCE_ADMIN_AUTH` | `false` | `true` |
| `ADMIN_API_KEY` | empty or placeholder | strong secret from secret manager |
| `ENABLE_INGEST_UI` | `false` | `false` (enable only for trusted operators) |
| `RETURN_CONTEXTS_IN_RESPONSE` | `false` | `false` |
| `CONTEXT_RESPONSE_MODE` | `none` | `none` or `redacted` |
| `RECONCILE_AUTORUN` | `false` | `true` |
| `RECONCILE_INTERVAL_SECONDS` | `300` | `300` (or lower if stricter monitoring needed) |

Why this split:
- Open-source users can run the app quickly without extra auth setup.
- Production operators keep critical data-changing endpoints protected.

### Important Note About `LLM_MODEL_PATH`

The code expects a model path or model identifier that `transformers` can load with:

- `AutoTokenizer.from_pretrained(...)`
- `AutoModelForCausalLM.from_pretrained(...)`

If the model is not available locally, the first load may require a download depending on your environment.

## Installation

Create a virtual environment and install dependencies:

```powershell
python -m venv .taxtenv
.taxtenv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Start Local Infrastructure

Bring up full stack (API + DynamoDB Local + ChromaDB):

```powershell
docker compose up -d
```

Expected ports:

- API: `8080`
- DynamoDB Local: `8000`
- ChromaDB HTTP API: `8001`

Notes:
- In Docker Compose, API container uses internal service names (`chromadb`, `dynamodb-local`).
- For local non-container runs, keep `.env` values at localhost defaults.

To stop containers:

```powershell
docker compose down
```

To stop containers and remove persisted local volumes:

```powershell
docker compose down -v
```

## Run The API

Local non-container run:

```powershell
uvicorn src.api.main:app --reload --port 8080
```

Health endpoint:

- `GET /`

Main endpoints:

- `POST /api/v1/ingest`
- `POST /api/v1/retrieve`
- `GET /api/v1/reconcile`
- `GET /api/v1/reconcile/last`
- `POST /api/v1/reconcile/repair`

When `ENFORCE_ADMIN_AUTH=true`, admin endpoints require header:

- `X-Admin-Key: <ADMIN_API_KEY>`

Protected endpoints:
- `POST /api/v1/ingest`
- `GET /api/v1/reconcile`
- `GET /api/v1/reconcile/last`
- `POST /api/v1/reconcile/repair`

## Run The Streamlit UI

```powershell
streamlit run src/frontend/app.py
```

The UI is a thin client over the API:

- Left side: document ingest
- Right side: retrieval and answer generation

## API Examples

### Ingest A Document

```powershell
curl -X POST http://localhost:8080/api/v1/ingest `
  -H "Content-Type: application/json" `
  -d "{\"document_text\":\"VAT on hotel stays in Sweden may use a reduced rate of 12 percent.\",\"source_name\":\"hotel_vat_notes.txt\"}"
```

### Ask A Question

```powershell
curl -X POST http://localhost:8080/api/v1/retrieve `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"What tax rate applies to staying in a hotel?\",\"top_k\":2}"
```

## Tests

Run the automated unit tests:

```powershell
pytest -q
```

Run integration test (requires local Docker services + encryption key):

```powershell
pytest -q -m integration
```

Optional manual DB inspection:

```powershell
python tests\inspect_dbs.py
```

## CI Quality Gate

GitHub Actions (`.github/workflows/ci.yml`) runs these checks on `push` and `pull_request`:
- lint sanity gate (`ruff`, selected critical rules: syntax/undefined-name class errors)
- import smoke for core modules
- unit test suite (`pytest -q -m "not integration"`)

Integration tests are still available locally:

```powershell
pytest -q -m integration
```

## Configuration Notes

Relevant values in `src/core/config.py`:

- `API_PORT`
- `API_BASE_URL`
- `CHROMA_HOST`
- `CHROMA_PORT`
- `DYNAMO_ENDPOINT`
- `DYNAMO_REGION`
- `MASTER_ENCRYPTION_KEY`
- `LLM_MODEL_PATH`
- `EMBEDDING_MODEL`
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `LLM_MAX_NEW_TOKENS`
- `LLM_TEMPERATURE`
- `RETURN_CONTEXTS_IN_RESPONSE`
- `CONTEXT_RESPONSE_MODE`
- `RECONCILE_AUTORUN`
- `RECONCILE_INTERVAL_SECONDS`
- `ENFORCE_ADMIN_AUTH`
- `ADMIN_API_KEY`

`CONTEXT_RESPONSE_MODE` behaviors:
- `none`: never include contexts in API responses
- `redacted`: include metadata only (context index and character count)
- `full`: include full decrypted contexts (if `ENFORCE_ADMIN_AUTH=true`, valid admin key is required to see full contexts)

At the moment, not every module actually respects these settings consistently. Some database connection values are still hard-coded in the client classes.

## Security Model

The repository is designed around a simple rule:

- Do not store raw document text inside the vector database.

Current behavior:

- ChromaDB stores embeddings and chunk IDs
- DynamoDB stores encrypted chunk text
- Decryption happens inside the application before generation

This is a reasonable prototype pattern, but the current API still returns decrypted context to the caller. That is convenient for debugging, but it weakens the security story and should probably become optional or be removed in a hardened version.

## Known Limitations

- Importing the LLM module triggers immediate model loading
- Importing storage modules can trigger real local infrastructure access
- Ingest writes are not atomic across both databases
- Error handling is basic and mostly returns generic `500` responses
- Metadata handling is incomplete and inconsistent
- The frontend is useful for demos but not hardened for operational use
- There is no CI pipeline, Dockerfile for the app, or production deployment path yet
- The repository currently includes generated and stateful artifacts that should usually be excluded from version control

## Suggested Next Steps

See `ADVICE.md` for a prioritized improvement plan.

High-level direction:

1. Remove import-time side effects and use dependency injection
2. Centralize configuration usage
3. Replace script-style tests with automated unit and integration tests
4. Add failure handling for partial ingest writes
5. Tighten the security boundary around decrypted text

## Reconciliation Runbook

Use this runbook when Chroma and Dynamo drift apart.

1. Detect drift

```powershell
curl http://localhost:8080/api/v1/reconcile
```

2. Review categories
- `only_in_chroma`: vector exists but encrypted text does not.
- `only_in_dynamo`: encrypted text exists but vector does not.

3. Choose repair strategy
- `only_in_chroma_action=delete` removes orphan vectors.
- `only_in_dynamo_action=rehydrate` decrypts Dynamo chunk and recreates vector.
- `mark_for_review` leaves records untouched and flags them in response.

4. Execute repair

```powershell
curl -X POST http://localhost:8080/api/v1/reconcile/repair `
  -H "Content-Type: application/json" `
  -d "{\"only_in_chroma_action\":\"delete\",\"only_in_dynamo_action\":\"rehydrate\"}"
```

5. Validate final state

```powershell
curl http://localhost:8080/api/v1/reconcile/last
```

If `is_consistent=false` remains after repair, inspect `failed` and `marked_for_review` lists and triage those IDs manually.

## License

No license file is present in the repository yet. Add one before public distribution.
