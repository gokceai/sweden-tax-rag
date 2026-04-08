import logging

from fastapi import FastAPI, HTTPException

from src.api.schemas import IngestRequest, QueryRequest
from src.core.config import settings
from src.core.dependencies import get_answer_generator, get_rag_engine
from src.core.exceptions import AppError

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
)


@app.get("/")
def health_check():
    return {"status": "ACTIVE", "service": settings.PROJECT_NAME}


@app.post("/api/v1/ingest", summary="Upload New Document")
def ingest_document(request: IngestRequest):
    try:
        rag_engine = get_rag_engine()
        chunks_saved = rag_engine.ingest_document(request.document_text, request.source_name)
        return {
            "message": "The document was successfully processed and securely stored.",
            "chunks_processed": chunks_saved,
            "source": request.source_name,
        }
    except AppError as e:
        logger.error("Ingest application error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unhandled ingest error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected ingest failure.") from e


@app.post("/api/v1/retrieve", summary="Ask a question and get an AI answer")
def retrieve_and_generate(request: QueryRequest):
    try:
        rag_engine = get_rag_engine()
        answer_generator = get_answer_generator()
        contexts = rag_engine.retrieve_context(request.query, request.top_k)

        if not contexts:
            return {
                "query": request.query,
                "answer": settings.WARNING_PROMPT,
                "contexts": [] if settings.RETURN_CONTEXTS_IN_RESPONSE else None,
            }

        ai_answer = answer_generator.generate_answer(request.query, contexts)
        return {
            "query": request.query,
            "answer": ai_answer,
            "contexts": contexts if settings.RETURN_CONTEXTS_IN_RESPONSE else None,
        }
    except AppError as e:
        logger.error("Retrieve application error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unhandled retrieve error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected retrieval failure.") from e


@app.get("/api/v1/reconcile", summary="Check Chroma and Dynamo consistency")
def reconcile_storage():
    try:
        rag_engine = get_rag_engine()
        return rag_engine.reconcile_indexes()
    except AppError as e:
        logger.error("Reconcile application error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unhandled reconcile error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected reconcile failure.") from e
