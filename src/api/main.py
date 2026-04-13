import logging
import threading
import time
import uuid
import json
import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from src.api.schemas import IngestRequest, QueryRequest, ReconcileRepairRequest
from src.core.config import settings
from src.core.dependencies import (
    get_answer_generator,
    get_document_repository,
    get_rag_engine,
    get_vector_db_manager,
    require_admin_access,
)
from src.core.exceptions import AppError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.last_reconcile_result = None
    app.state.reconcile_stop_event = threading.Event()
    app.state.reconcile_thread = None
    app.state.llm_warmup_thread = None

    if settings.LLM_EAGER_LOAD:
        def _warmup_llm():
            try:
                logger.info("LLM warmup starting in background thread...")
                get_answer_generator().load()
                logger.info("LLM warmup complete.")
            except Exception as exc:
                logger.error("LLM warmup failed: %s", exc)

        warmup_thread = threading.Thread(target=_warmup_llm, daemon=True, name="llm-warmup")
        warmup_thread.start()
        app.state.llm_warmup_thread = warmup_thread

    if settings.RECONCILE_AUTORUN:
        worker = threading.Thread(
            target=_run_scheduled_reconcile,
            args=(app.state.reconcile_stop_event,),
            daemon=True,
            name="reconcile-worker",
        )
        worker.start()
        app.state.reconcile_thread = worker

    yield

    stop_event = getattr(app.state, "reconcile_stop_event", None)
    worker = getattr(app.state, "reconcile_thread", None)
    if stop_event is not None:
        stop_event.set()
    if worker is not None:
        worker.join(timeout=2)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
RAG_RETRIEVE_REQUESTS_TOTAL = Counter(
    "rag_retrieve_requests_total",
    "Total retrieve requests by outcome",
    ["outcome"],
)
RAG_RETRIEVE_DURATION_SECONDS = Histogram(
    "rag_retrieve_duration_seconds",
    "Retrieve endpoint duration in seconds",
    ["outcome"],
)
RAG_INGEST_REQUESTS_TOTAL = Counter(
    "rag_ingest_requests_total",
    "Total ingest requests by outcome",
    ["outcome"],
)
RAG_INGEST_CHUNKS_TOTAL = Counter(
    "rag_ingest_chunks_total",
    "Total number of chunks successfully written by ingest flow",
)
RAG_INGEST_DURATION_SECONDS = Histogram(
    "rag_ingest_duration_seconds",
    "Ingest endpoint duration in seconds",
    ["outcome"],
)
RAG_RECONCILE_RUNS_TOTAL = Counter(
    "rag_reconcile_runs_total",
    "Total reconcile runs by source and outcome",
    ["source", "outcome"],
)
RAG_RECONCILE_ONLY_IN_CHROMA = Gauge(
    "rag_reconcile_only_in_chroma",
    "Current count of chunk IDs present only in Chroma",
)
RAG_RECONCILE_ONLY_IN_DOCUMENT_STORE = Gauge(
    "rag_reconcile_only_in_document_store",
    "Current count of chunk IDs present only in the document store (SQLite)",
)
RAG_RECONCILE_IS_CONSISTENT = Gauge(
    "rag_reconcile_is_consistent",
    "Consistency status from latest reconcile run (1=true, 0=false)",
)
RAG_REPAIR_REQUESTS_TOTAL = Counter(
    "rag_repair_requests_total",
    "Total repair requests by outcome and actions",
    ["outcome", "only_in_chroma_action", "only_in_document_store_action"],
)
RAG_REPAIR_DURATION_SECONDS = Histogram(
    "rag_repair_duration_seconds",
    "Repair endpoint duration in seconds",
    ["outcome"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    path = request.url.path
    method = request.method
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        _log_event(
            "error",
            "request_failed",
            request_id=request_id,
            method=method,
            path=path,
            status_code=500,
            duration_ms=duration_ms,
            error_code="unhandled_exception",
            error_category="server_error",
        )
        logger.exception("Unhandled middleware error")
        raise
    finally:
        duration_s = time.perf_counter() - started_at
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_s)
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            path=path,
            status_code=str(status_code),
        ).inc()

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    _log_event(
        "info",
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_event(level: str, event: str, **fields):
    payload = {"event": event, **fields}
    message = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)


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
    _log_event(
        "warning",
        "http_exception",
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=exc.status_code,
        error_code=detail.get("error_code"),
        error_category=detail.get("error_category"),
        message=detail.get("message"),
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


def _has_valid_admin_key(request: Request) -> bool:
    if not settings.ADMIN_API_KEY:
        return False
    provided = request.headers.get("X-Admin-Key")
    if not provided:
        return False
    return hmac.compare_digest(provided, settings.ADMIN_API_KEY)


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
            _record_reconcile_metrics(report, source="scheduled_job", outcome="success")
            app.state.last_reconcile_result = {
                "report": report,
                "checked_at": _utc_now_iso(),
                "source": "scheduled_job",
            }
        except Exception as e:
            _log_event(
                "error",
                "scheduled_reconcile_error",
                error_code="reconcile_scheduled_error",
                error_category="server_error",
                message=str(e),
            )
            logger.exception("Scheduled reconcile failed: %s", e)
            RAG_RECONCILE_RUNS_TOTAL.labels(source="scheduled_job", outcome="error").inc()
            app.state.last_reconcile_result = {
                "report": None,
                "checked_at": _utc_now_iso(),
                "source": "scheduled_job",
                "error": str(e),
            }
        stop_event.wait(settings.RECONCILE_INTERVAL_SECONDS)


@app.get("/ping", include_in_schema=False)
def ping():
    return {"status": "ACTIVE", "service": settings.PROJECT_NAME}


@app.get("/health/live", include_in_schema=False)
def health_live():
    return {"status": "ok", "service": settings.PROJECT_NAME, "mode": "live"}


@app.get("/health/ready", include_in_schema=False)
def health_ready():
    checks = {
        "vector_db": {"ok": False, "message": None},
        "document_store": {"ok": False, "message": None},
        "llm": {"ok": False, "message": None},
    }
    overall_ok = True

    try:
        _ = get_vector_db_manager().collection_name
        checks["vector_db"]["ok"] = True
    except Exception as e:
        overall_ok = False
        checks["vector_db"]["message"] = "unavailable"
        logger.warning("Ready check failed for vector_db: %s", e)

    try:
        ok = get_document_repository().ping()
        if not ok:
            raise RuntimeError("SQLite ping returned False")
        checks["document_store"]["ok"] = True
    except Exception as e:
        overall_ok = False
        checks["document_store"]["message"] = "unavailable"
        logger.warning("Ready check failed for document_store: %s", e)

    try:
        generator = get_answer_generator()
        if generator.is_ready:
            checks["llm"]["ok"] = True
        elif generator.has_error:
            checks["llm"]["message"] = "load_failed"
            overall_ok = False
            logger.warning("Ready check: LLM failed to load.")
        else:
            checks["llm"]["message"] = "loading"
            # Still warming up — informational only, does not block readiness
    except Exception as e:
        checks["llm"]["message"] = "unavailable"
        logger.warning("Ready check failed for llm: %s", e)

    payload = {"status": "ok" if overall_ok else "degraded", "mode": "ready", "checks": checks}
    if overall_ok:
        return payload
    raise HTTPException(status_code=503, detail=payload)


@app.get("/health/deep", include_in_schema=False)
def health_deep():
    checks = {
        "vector_db_query": {"ok": False, "message": None},
        "document_store_scan": {"ok": False, "message": None},
    }
    overall_ok = True

    try:
        _ = get_vector_db_manager().search_similar_ids("swedish tax health check", n_results=1)
        checks["vector_db_query"]["ok"] = True
    except Exception as e:
        overall_ok = False
        checks["vector_db_query"]["message"] = "unavailable"
        logger.warning("Deep check failed for vector_db_query: %s", e)

    try:
        _ = get_document_repository().list_chunk_ids()
        checks["document_store_scan"]["ok"] = True
    except Exception as e:
        overall_ok = False
        checks["document_store_scan"]["message"] = "unavailable"
        logger.warning("Deep check failed for document_store_scan: %s", e)

    payload = {"status": "ok" if overall_ok else "degraded", "mode": "deep", "checks": checks}
    if overall_ok:
        return payload
    raise HTTPException(status_code=503, detail=payload)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _record_reconcile_metrics(report: dict, *, source: str, outcome: str):
    RAG_RECONCILE_RUNS_TOTAL.labels(source=source, outcome=outcome).inc()
    only_in_chroma = report.get("only_in_chroma", [])
    only_in_document_store = report.get("only_in_document_store", [])
    RAG_RECONCILE_ONLY_IN_CHROMA.set(len(only_in_chroma))
    RAG_RECONCILE_ONLY_IN_DOCUMENT_STORE.set(len(only_in_document_store))
    RAG_RECONCILE_IS_CONSISTENT.set(1 if report.get("is_consistent") else 0)


@app.post("/api/v1/ingest", summary="Upload New Document")
def ingest_document(
    request: IngestRequest,
    raw_request: Request,
    _: None = Depends(require_admin_access),
):
    started_at = time.perf_counter()
    outcome = "error"
    try:
        rag_engine = get_rag_engine()
        chunks_saved = rag_engine.ingest_document(request.document_text, request.source_name)
        RAG_INGEST_CHUNKS_TOTAL.inc(chunks_saved)
        outcome = "success"
        return {
            "message": "The document was successfully processed and securely stored.",
            "chunks_processed": chunks_saved,
            "source": request.source_name,
        }
    except AppError as e:
        _log_event(
            "error",
            "ingest_error",
            request_id=getattr(raw_request.state, "request_id", None),
            error_code="ingest_app_error",
            error_category=_error_category(e.status_code),
            status_code=e.status_code,
            message=e.message,
        )
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
    finally:
        duration_s = time.perf_counter() - started_at
        RAG_INGEST_REQUESTS_TOTAL.labels(outcome=outcome).inc()
        RAG_INGEST_DURATION_SECONDS.labels(outcome=outcome).observe(duration_s)


@app.post("/api/v1/retrieve", summary="Ask a question and get an AI answer")
def retrieve_and_generate(request: QueryRequest, raw_request: Request):
    started_at = time.perf_counter()
    outcome = "error"
    try:
        rag_engine = get_rag_engine()
        answer_generator = get_answer_generator()
        contexts = rag_engine.retrieve_context(request.query, request.top_k)

        if not contexts:
            outcome = "empty"
            return {
                "query": request.query,
                "answer": settings.WARNING_PROMPT,
                "contexts": _build_context_payload([], raw_request),
            }

        ai_answer = answer_generator.generate_answer(request.query, contexts)
        outcome = "success"
        return {
            "query": request.query,
            "answer": ai_answer,
            "contexts": _build_context_payload(contexts, raw_request),
        }
    except AppError as e:
        _log_event(
            "error",
            "retrieve_error",
            request_id=getattr(raw_request.state, "request_id", None),
            error_code="retrieve_app_error",
            error_category=_error_category(e.status_code),
            status_code=e.status_code,
            message=e.message,
        )
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
    finally:
        duration_s = time.perf_counter() - started_at
        RAG_RETRIEVE_REQUESTS_TOTAL.labels(outcome=outcome).inc()
        RAG_RETRIEVE_DURATION_SECONDS.labels(outcome=outcome).observe(duration_s)


@app.get("/api/v1/reconcile", summary="Check Chroma and SQLite consistency")
def reconcile_storage(
    raw_request: Request,
    _: None = Depends(require_admin_access),
):
    outcome = "error"
    try:
        rag_engine = get_rag_engine()
        report = rag_engine.reconcile_indexes()
        outcome = "success"
        _record_reconcile_metrics(report, source="manual_api", outcome=outcome)
        app.state.last_reconcile_result = {
            "report": report,
            "checked_at": _utc_now_iso(),
            "source": "manual_api",
        }
        return report
    except AppError as e:
        _log_event(
            "error",
            "reconcile_error",
            request_id=getattr(raw_request.state, "request_id", None),
            error_code="reconcile_app_error",
            error_category=_error_category(e.status_code),
            status_code=e.status_code,
            message=e.message,
        )
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
    finally:
        if outcome != "success":
            RAG_RECONCILE_RUNS_TOTAL.labels(source="manual_api", outcome="error").inc()


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


@app.post("/api/v1/reconcile/repair", summary="Repair Chroma/SQLite inconsistencies")
def repair_storage(
    request: ReconcileRepairRequest,
    raw_request: Request,
    _: None = Depends(require_admin_access),
):
    started_at = time.perf_counter()
    outcome = "error"
    try:
        rag_engine = get_rag_engine()
        repair_report = rag_engine.repair_indexes(
            only_in_chroma_action=request.only_in_chroma_action,
            only_in_document_store_action=request.only_in_document_store_action,
        )
        outcome = "success"
        post_reconcile = repair_report.get("post_reconcile", {})
        if post_reconcile:
            _record_reconcile_metrics(post_reconcile, source="repair_api", outcome=outcome)
        app.state.last_reconcile_result = {
            "report": repair_report.get("post_reconcile"),
            "checked_at": _utc_now_iso(),
            "source": "repair_api",
        }
        return repair_report
    except AppError as e:
        _log_event(
            "error",
            "repair_error",
            request_id=getattr(raw_request.state, "request_id", None),
            error_code="repair_app_error",
            error_category=_error_category(e.status_code),
            status_code=e.status_code,
            message=e.message,
        )
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
    finally:
        duration_s = time.perf_counter() - started_at
        RAG_REPAIR_REQUESTS_TOTAL.labels(
            outcome=outcome,
            only_in_chroma_action=request.only_in_chroma_action,
            only_in_document_store_action=request.only_in_document_store_action,
        ).inc()
        RAG_REPAIR_DURATION_SECONDS.labels(outcome=outcome).observe(duration_s)


# ---------------------------------------------------------------------------
# Gradio UI — mounted at "/" so HF Spaces shows the UI on the root path.
# API routes defined above (/api/v1/*, /health/*, /metrics) take precedence.
# ---------------------------------------------------------------------------
import gradio as gr  # noqa: E402
from src.frontend.app import app as _gradio_demo  # noqa: E402

gr.mount_gradio_app(app, _gradio_demo, path="/", ssr_mode=False)
