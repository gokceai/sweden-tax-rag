import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Project metadata
    PROJECT_NAME = "Swedish Tax Law RAG Assistant"
    PROJECT_VERSION = "1.0.0"
    PROJECT_DESCRIPTION = "RAG engine with encryption for Swedish tax laws."

    # Network
    API_PORT = int(os.getenv("API_PORT", 7860))

    # ChromaDB
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./docker/chroma_data")
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "swedish_tax_vectors")
    CHROMA_DISTANCE = os.getenv("CHROMA_DISTANCE", "cosine")

    # SQLite encrypted document store
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./docker/documents.db")

    # Encryption
    MASTER_ENCRYPTION_KEY = os.getenv("MASTER_ENCRYPTION_KEY")

    # LLM & embeddings
    LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "meta-llama/Llama-3.2-1B-Instruct")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "auto").lower()
    LLM_DEVICE = os.getenv("LLM_DEVICE", "auto").lower()
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 400))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))
    LLM_MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", 250))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.1))
    LLM_EAGER_LOAD = os.getenv("LLM_EAGER_LOAD", "true").lower() == "true"

    @staticmethod
    def resolve_device(preference: str = "auto") -> str:
        if preference in ("cpu", "cuda", "mps"):
            return preference
        try:
            import torch  # noqa: PLC0415
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    SYSTEM_PROMPT = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are an elite Swedish Tax Advisor AI. Your task is to answer the user's question accurately using ONLY the provided context.
If the answer cannot be found in the context, say "Based on the provided documents, I cannot answer this." Do not hallucinate or use outside knowledge.
Keep your answer professional, clear, and concise.

CONTEXT:
{context}<|eot_id|><|start_header_id|>user<|end_header_id|>
QUESTION: {query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    WARNING_PROMPT = "I am sorry, but I couldn't find any relevant legal documents to answer your question."


settings = Settings()
