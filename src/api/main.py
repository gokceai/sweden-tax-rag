import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.schemas import IngestRequest, QueryRequest, ReconcileRepairRequest
from src.core.config import settings
from src.core.dependencies import get_answer_generator, get_rag_engine, require_admin_access
from src.core.exceptions import AppError

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_category(status_code: int) -> str:
    if status_code in (401, 403):
        return "auth_error"
    if 400 <= status_code < 500:
        return "client_error"
    if status_code == 503:
        return "infrastructure_error"
    return "server_error"


def _error_detail(message: str, *, error_code: str, status_code: int, request: Request) -> dict:
    return {
        "message": message,
        "error_code": error_code,
        "error_category": _error_category(status_code),
        "request_id": getattr(request.state, "request_id", None),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        detail = exc.detail
    else:
        detail = _error_detail(
            str(exc.detail),
            error_code="http_error",
            status_code=exc.status_code,
            request=request,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


def _has_valid_admin_key(request: Request) -> bool:
    if not settings.ADMIN_API_KEY:
        return False
    return request.headers.get("X-Admin-Key") == settings.ADMIN_API_KEY


def _build_context_payload(contexts: list[str], request: Request):
    if not settings.RETURN_CONTEXTS_IN_RESPONSE:
        return None

    mode = settings.CONTEXT_RESPONSE_MODE
    if mode == "full":
        if settings.ENFORCE_ADMIN_AUTH and not _has_valid_admin_key(request):
            return None
        return contexts

    if mode == "redacted":
        return [{"index": i + 1, "char_count": len(ctx)} for i, ctx in enumerate(contexts)]

    return None


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
def ingest_document(
    request: IngestRequest,
    raw_request: Request,
    _: None = Depends(require_admin_access),
):
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
        raise HTTPException(
            status_code=e.status_code,
            detail=_error_detail(
                e.message,
                error_code="ingest_app_error",
                status_code=e.status_code,
                request=raw_request,
            ),
        ) from e
    except Exception as e:
        logger.exception("Unhandled ingest error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "Unexpected ingest failure.",
                error_code="ingest_unexpected_error",
                status_code=500,
                request=raw_request,
            ),
        ) from e


@app.post("/api/v1/retrieve", summary="Ask a question and get an AI answer")
def retrieve_and_generate(request: QueryRequest, raw_request: Request):
    try:
        rag_engine = get_rag_engine()
        answer_generator = get_answer_generator()
        contexts = rag_engine.retrieve_context(request.query, request.top_k)

        if not contexts:
            return {
                "query": request.query,
                "answer": settings.WARNING_PROMPT,
                "contexts": _build_context_payload([], raw_request),
            }

        ai_answer = answer_generator.generate_answer(request.query, contexts)
        return {
            "query": request.query,
            "answer": ai_answer,
            "contexts": _build_context_payload(contexts, raw_request),
        }
    except AppError as e:
        logger.error("Retrieve application error: %s", e.message)
        raise HTTPException(
            status_code=e.status_code,
            detail=_error_detail(
                e.message,
                error_code="retrieve_app_error",
                status_code=e.status_code,
                request=raw_request,
            ),
        ) from e
    except Exception as e:
        logger.exception("Unhandled retrieve error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "Unexpected retrieval failure.",
                error_code="retrieve_unexpected_error",
                status_code=500,
                request=raw_request,
            ),
        ) from e


@app.get("/api/v1/reconcile", summary="Check Chroma and Dynamo consistency")
def reconcile_storage(
    raw_request: Request,
    _: None = Depends(require_admin_access),
):
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
        raise HTTPException(
            status_code=e.status_code,
            detail=_error_detail(
                e.message,
                error_code="reconcile_app_error",
                status_code=e.status_code,
                request=raw_request,
            ),
        ) from e
    except Exception as e:
        logger.exception("Unhandled reconcile error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "Unexpected reconcile failure.",
                error_code="reconcile_unexpected_error",
                status_code=500,
                request=raw_request,
            ),
        ) from e


@app.get("/api/v1/reconcile/last", summary="Get last reconciliation result")
def get_last_reconcile_result(
    _: None = Depends(require_admin_access),
):
    result = getattr(app.state, "last_reconcile_result", None)
    if not result:
        return {
            "message": "No reconciliation has been run yet.",
            "result": None,
        }
    return result


@app.post("/api/v1/reconcile/repair", summary="Repair Chroma/Dynamo inconsistencies")
def repair_storage(
    request: ReconcileRepairRequest,
    raw_request: Request,
    _: None = Depends(require_admin_access),
):
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
        raise HTTPException(
            status_code=e.status_code,
            detail=_error_detail(
                e.message,
                error_code="repair_app_error",
                status_code=e.status_code,
                request=raw_request,
            ),
        ) from e
    except Exception as e:
        logger.exception("Unhandled repair error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "Unexpected repair failure.",
                error_code="repair_unexpected_error",
                status_code=500,
                request=raw_request,
            ),
        ) from e
