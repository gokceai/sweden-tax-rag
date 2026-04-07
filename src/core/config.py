import os
from dotenv import load_dotenv

# We only upload the .env file here once for the entire project.
load_dotenv()

class Settings:
    # --- Project Metadatas ---
    PROJECT_NAME = "Swedish Tax Law RAG Oracle"
    PROJECT_VERSION = "1.0.0"
    PROJECT_DESCRIPTION = "RAG engine with encryption for Swedish tax laws."

    # --- Network and Port Settings ---
    API_PORT = int(os.getenv("API_PORT", 8080))
    API_BASE_URL = os.getenv("API_BASE_URL", f"http://localhost:{API_PORT}/api/v1")
    
    # --- Database Settings ---
    CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8001))
    DYNAMO_ENDPOINT = os.getenv("DYNAMO_ENDPOINT", "http://localhost:8000")
    DYNAMO_REGION = os.getenv("DYNAMO_REGION", "eu-north-1")

    # --- Security ---
    MASTER_ENCRYPTION_KEY = os.getenv("MASTER_ENCRYPTION_KEY")

    # --- Artificial Intelligence (AI) & RAG Settings ---
    LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "meta-llama/Llama-3.2-1B-Instruct")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHUNK_SIZE = 400
    CHUNK_OVERLAP = 50
    LLM_MAX_NEW_TOKENS = 250
    LLM_TEMPERATURE = 0.1

    # --- LLM Main Prompt (Character and Rules) ---
    SYSTEM_PROMPT = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are an elite Swedish Tax Advisor AI. Your task is to answer the user's question accurately using ONLY the provided context.
If the answer cannot be found in the context, say "Based on the provided documents, I cannot answer this." Do not hallucinate or use outside knowledge.
Keep your answer professional, clear, and concise.

CONTEXT:
{context}<|eot_id|><|start_header_id|>user<|end_header_id|>
QUESTION: {query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
    WARNING_PROMPT = """I am sorry, but I couldn't find any relevant legal documents to answer your question."""
# We will call this object throughout the entire project.
settings = Settings()