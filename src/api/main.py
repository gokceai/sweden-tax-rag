from fastapi import FastAPI, HTTPException
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.api.schemas import IngestRequest, QueryRequest
from src.engine.rag_core import rag_engine
from src.engine.llm_engine import llm_oracle 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Swedish Tax Law RAG Oracle API",
    description="RAG engine with encryption for Swedish tax laws.",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {"status": "ACTIVE", "service": "Swedish Tax RAG Oracle"}

@app.post("/api/v1/ingest", summary="Upload New Document")
def ingest_document(request: IngestRequest):
    try:
        chunks_saved = rag_engine.ingest_document(request.document_text, request.source_name)
        return {
            "message": "The document was successfully processed and securely stored.",
            "chunks_processed": chunks_saved,
            "source": request.source_name
        }
    except Exception as e:
        logger.error(f"Ingest Error: {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing the document.")

@app.post("/api/v1/retrieve", summary="Ask a question and get an AI answer")
def retrieve_and_generate(request: QueryRequest):
    """It searches for the question, deciphers the encrypted text, and produces a humanoid answer with Llama 3.2"""
    try:
        # 1.Retrieve contexts from memory.
        contexts = rag_engine.retrieve_context(request.query, request.top_k)
        
        if not contexts:
            return {
                "query": request.query, 
                "answer": "Based on the provided documents, I cannot answer this.", 
                "contexts": []
            }
        
        # 2. Generate an answer using llm.
        ai_answer = llm_oracle.generate_answer(request.query, contexts)
        
        return {
            "query": request.query, 
            "answer": ai_answer, 
            "contexts": contexts
        }
    except Exception as e:
        logger.error(f"Retrieve Hatası: {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred while generating the response.")