import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from src.api.schemas import IngestRequest, QueryRequest, ReconcileRepairRequest
from src.core.config import settings
from src.core.dependencies import get_answer_generator, get_rag_engine
from src.core.exceptions import AppError

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_scheduled_reconcile(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            report = get_rag_engine().reconcile_indexes()
            app.state.last_reconcile_result = {
                "report": report,
                "checked_at": _utc_now_iso(),
                "source": "scheduled_job",
            }
        except Exception as e:
            logger.exception("Scheduled reconcile failed: %s", e)
            app.state.last_reconcile_result = {
                "report": None,
                "checked_at": _utc_now_iso(),
                "source": "scheduled_job",
                "error": str(e),
            }
        stop_event.wait(settings.RECONCILE_INTERVAL_SECONDS)


@app.on_event("startup")
def startup_reconcile_worker():
    app.state.last_reconcile_result = None
    app.state.reconcile_stop_event = threading.Event()
    app.state.reconcile_thread = None

    if not settings.RECONCILE_AUTORUN:
        return

    worker = threading.Thread(
        target=_run_scheduled_reconcile,
        args=(app.state.reconcile_stop_event,),
        daemon=True,
        name="reconcile-worker",
    )
    worker.start()
    app.state.reconcile_thread = worker


@app.on_event("shutdown")
def shutdown_reconcile_worker():
    stop_event = getattr(app.state, "reconcile_stop_event", None)
    worker = getattr(app.state, "reconcile_thread", None)
    if stop_event is not None:
        stop_event.set()
    if worker is not None:
        worker.join(timeout=2)


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
        report = rag_engine.reconcile_indexes()
        app.state.last_reconcile_result = {
            "report": report,
            "checked_at": _utc_now_iso(),
            "source": "manual_api",
        }
        return report
    except AppError as e:
        logger.error("Reconcile application error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unhandled reconcile error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected reconcile failure.") from e


@app.get("/api/v1/reconcile/last", summary="Get last reconciliation result")
def get_last_reconcile_result():
    result = getattr(app.state, "last_reconcile_result", None)
    if not result:
        return {
            "message": "No reconciliation has been run yet.",
            "result": None,
        }
    return result


@app.post("/api/v1/reconcile/repair", summary="Repair Chroma/Dynamo inconsistencies")
def repair_storage(request: ReconcileRepairRequest):
    try:
        rag_engine = get_rag_engine()
        repair_report = rag_engine.repair_indexes(
            only_in_chroma_action=request.only_in_chroma_action,
            only_in_dynamo_action=request.only_in_dynamo_action,
        )
        app.state.last_reconcile_result = {
            "report": repair_report.get("post_reconcile"),
            "checked_at": _utc_now_iso(),
            "source": "repair_api",
        }
        return repair_report
    except AppError as e:
        logger.error("Repair application error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unhandled repair error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected repair failure.") from e
