import logging
import os
import threading

import gradio as gr
from fastapi import FastAPI, HTTPException

from src.api.schemas import QueryRequest
from src.core.config import settings
from src.core.dependencies import get_answer_generator, get_rag_engine
from src.core.exceptions import AppError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
)


@app.get("/ping", include_in_schema=False)
def ping():
    return {"status": "ACTIVE", "service": settings.PROJECT_NAME}


@app.get("/health/live", include_in_schema=False)
def health_live():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def health_ready():
    from src.core.dependencies import get_document_repository, get_vector_db_manager

    checks = {}
    ok = True
    try:
        _ = get_vector_db_manager().collection_name
        checks["vector_db"] = "ok"
    except Exception:
        checks["vector_db"] = "unavailable"
        ok = False
    try:
        if not get_document_repository().ping():
            raise RuntimeError("ping returned False")
        checks["document_store"] = "ok"
    except Exception:
        checks["document_store"] = "unavailable"
        ok = False
    gen = get_answer_generator()
    if gen.is_ready:
        checks["llm"] = "ok"
    elif gen.has_error:
        checks["llm"] = "load_failed"
        ok = False
    else:
        checks["llm"] = "loading"
    payload = {"status": "ok" if ok else "degraded", "checks": checks}
    if ok:
        return payload
    raise HTTPException(status_code=503, detail=payload)


@app.post("/api/v1/retrieve", summary="Ask a question and get an AI answer")
def retrieve_and_generate(request: QueryRequest):
    try:
        contexts = get_rag_engine().retrieve_context(request.query, request.top_k)
        if not contexts:
            return {"query": request.query, "answer": settings.WARNING_PROMPT}
        answer = get_answer_generator().generate_answer(request.query, contexts)
        return {"query": request.query, "answer": answer}
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unhandled retrieve error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected retrieval failure.") from e


# ---------------------------------------------------------------------------
# Gradio UI
#
# We use gr.mount_gradio_app (the supported public API) so that Gradio's own
# lifespan and static-file serving are fully initialised.
#
# Root-path fix: HF Spaces proxies do not forward x-forwarded-host, so
# Gradio would compute root="http://0.0.0.0:7860" and the browser JS would
# call that internal address → blank screen / asset 404s.
# mount_gradio_app accepts an explicit root_path that overrides the header
# detection.  We derive the public URL from the SPACE_ID env var that HF
# injects into every container at runtime.
# ---------------------------------------------------------------------------
from src.frontend.app import build_app  # noqa: E402

_demo = build_app()

_root_path: str | None = None
if os.environ.get("SYSTEM") == "spaces":
    _space_id = os.environ.get("SPACE_ID", "")
    if "/" in _space_id:
        _author, _repo = _space_id.split("/", 1)
        _root_path = f"https://{_author.lower()}-{_repo.lower()}.hf.space"

gr.mount_gradio_app(app, _demo, path="/", ssr_mode=False, root_path=_root_path)

# ---------------------------------------------------------------------------
# LLM warmup — start immediately after the module loads so the model is ready
# by the time the first user request arrives.  This runs in a daemon thread
# so it does not block Uvicorn startup.
# ---------------------------------------------------------------------------
if settings.LLM_EAGER_LOAD:
    def _warmup():
        try:
            get_answer_generator().load()
        except Exception as exc:
            logger.error("LLM warmup failed: %s", exc)

    threading.Thread(target=_warmup, daemon=True, name="llm-warmup").start()
