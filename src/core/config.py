import os
from dotenv import load_dotenv

# Load environment variables once.
load_dotenv()

class Settings:
    # Project metadata
    PROJECT_NAME = "Swedish Tax Law RAG Assistant"
    PROJECT_VERSION = "1.0.0"
    PROJECT_DESCRIPTION = "RAG engine with encryption for Swedish tax laws."

    # Network and port settings
    API_PORT = int(os.getenv("API_PORT", 8080))
    API_BASE_URL = os.getenv("API_BASE_URL", f"http://localhost:{API_PORT}/api/v1")

    # Database settings
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./docker/chroma_data")
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "swedish_tax_vectors")
    CHROMA_DISTANCE = os.getenv("CHROMA_DISTANCE", "cosine")

    # SQLite encrypted document store (replaces DynamoDB Local)
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./docker/documents.db")

    # DynamoDB settings kept only for the one-time migration script (migrate_dynamo_to_sqlite.py).
    # Remove after migration is complete.
    DYNAMO_ENDPOINT = os.getenv("DYNAMO_ENDPOINT", "http://localhost:8000")
    DYNAMO_REGION = os.getenv("DYNAMO_REGION", "eu-north-1")
    DYNAMO_TABLE_NAME = os.getenv("DYNAMO_TABLE_NAME", "SwedishTaxDocuments")
    DYNAMO_ACCESS_KEY_ID = os.getenv("DYNAMO_ACCESS_KEY_ID", "test")
    DYNAMO_SECRET_ACCESS_KEY = os.getenv("DYNAMO_SECRET_ACCESS_KEY", "test")

    # Security
    MASTER_ENCRYPTION_KEY = os.getenv("MASTER_ENCRYPTION_KEY")
    RETURN_CONTEXTS_IN_RESPONSE = os.getenv("RETURN_CONTEXTS_IN_RESPONSE", "false").lower() == "true"
    CONTEXT_RESPONSE_MODE = os.getenv("CONTEXT_RESPONSE_MODE", "none").lower()
    ENABLE_INGEST_UI = os.getenv("ENABLE_INGEST_UI", "false").lower() == "true"
    RECONCILE_AUTORUN = os.getenv("RECONCILE_AUTORUN", "false").lower() == "true"
    RECONCILE_INTERVAL_SECONDS = int(os.getenv("RECONCILE_INTERVAL_SECONDS", 300))
    ENFORCE_ADMIN_AUTH = os.getenv("ENFORCE_ADMIN_AUTH", "false").lower() == "true"
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

    # Monitoring targets (SLO baselines)
    SLO_API_P95_LATENCY_MS = int(os.getenv("SLO_API_P95_LATENCY_MS", 2500))
    SLO_API_5XX_ERROR_RATE_PERCENT = float(os.getenv("SLO_API_5XX_ERROR_RATE_PERCENT", 1.0))
    SLO_RETRIEVE_SUCCESS_RATE_PERCENT = float(os.getenv("SLO_RETRIEVE_SUCCESS_RATE_PERCENT", 99.0))
    SLO_RECONCILE_MISMATCH_ALLOWED = int(os.getenv("SLO_RECONCILE_MISMATCH_ALLOWED", 0))
    SLO_RECONCILE_MAX_STALENESS_MINUTES = int(os.getenv("SLO_RECONCILE_MAX_STALENESS_MINUTES", 1440))

    # AI and RAG settings
    LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "meta-llama/Llama-3.2-1B-Instruct")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 400))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
    LLM_MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", 250))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.1))

    # LLM main prompt
    SYSTEM_PROMPT = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are an elite Swedish Tax Advisor AI. Your task is to answer the user's question accurately using ONLY the provided context.
If the answer cannot be found in the context, say "Based on the provided documents, I cannot answer this." Do not hallucinate or use outside knowledge.
Keep your answer professional, clear, and concise.

CONTEXT:
{context}<|eot_id|><|start_header_id|>user<|end_header_id|>
QUESTION: {query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
    WARNING_PROMPT = """I am sorry, but I couldn't find any relevant legal documents to answer your question."""

settings = Settings()
