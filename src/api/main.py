import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.api.schemas import QueryRequest
from src.core.config import settings
from src.core.dependencies import get_answer_generator, get_rag_engine
from src.core.exceptions import AppError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.LLM_EAGER_LOAD:
        import threading

        def _warmup():
            try:
                get_answer_generator().load()
            except Exception as exc:
                logger.error("LLM warmup failed: %s", exc)

        threading.Thread(target=_warmup, daemon=True, name="llm-warmup").start()
    yield


fastapi_app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
)


@fastapi_app.get("/ping", include_in_schema=False)
def ping():
    return {"status": "ACTIVE", "service": settings.PROJECT_NAME}


@fastapi_app.get("/health/live", include_in_schema=False)
def health_live():
    return {"status": "ok"}


@fastapi_app.get("/health/ready", include_in_schema=False)
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


@fastapi_app.post("/api/v1/retrieve", summary="Ask a question and get an AI answer")
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
# Gradio UI — Gradio-first: create the ASGI app from the demo, then add our
# FastAPI routes on top.  This is the HF Spaces–native pattern and avoids
# the blank-screen issue caused by gr.mount_gradio_app on a proxy that does
# not forward x-forwarded-host.
# ---------------------------------------------------------------------------
import gradio as gr  # noqa: E402
from gradio.routes import App  # noqa: E402

from src.frontend.app import build_app  # noqa: E402

_demo = build_app()

# On HF Spaces the proxy does not forward x-forwarded-host, so Gradio would
# compute root="http://0.0.0.0:7860" and the browser JS would try to call
# that internal address → blank screen.
# We set blocks.root_path BEFORE App.create_app() so the Gradio App picks it
# up at line:  self.root_path = blocks.root_path or ""
if os.environ.get("SYSTEM") == "spaces":
    _space_id = os.environ.get("SPACE_ID", "")
    if "/" in _space_id:
        _author, _repo = _space_id.split("/", 1)
        _demo.root_path = f"https://{_author.lower()}-{_repo.lower()}.hf.space"

# Build the Gradio ASGI app and mount our FastAPI routes onto it.
app = App.create_app(_demo, ssr_mode=False)
app.include_router(fastapi_app.router)

# Carry over the lifespan so LLM warmup still runs.
app.router.lifespan_context = fastapi_app.router.lifespan_context  # type: ignore
