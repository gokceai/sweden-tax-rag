import logging
import os
import threading

from src.core.config import settings
from src.core.dependencies import get_answer_generator
from src.frontend.app import build_app

logger = logging.getLogger(__name__)

_demo = build_app()

if settings.LLM_EAGER_LOAD:
    def _warmup():
        try:
            get_answer_generator().load()
        except Exception as exc:
            logger.error("LLM warmup failed: %s", exc)

    threading.Thread(target=_warmup, daemon=True, name="llm-warmup").start()


def _resolve_gradio_root_path() -> str | None:
    """Return a safe root_path for Gradio.

    Priority order:
    1. Explicit GRADIO_ROOT_PATH env var (full URL or path) — used as-is.
    2. HF Spaces: construct full HTTPS URL from SPACE_HOST so Gradio 5.x
       embeds the correct public origin in every /config response (bypasses
       unreliable x-forwarded-host detection on HF's nginx proxy).
    3. Otherwise return None (Gradio falls back to its own detection).

    Gradio 5.x get_root_url() short-circuits to the supplied value when it
    is a full http(s) URL, so passing the HF public URL here is the
    authoritative fix for the blank-page / wrong-root bug.
    """
    raw = (os.environ.get("GRADIO_ROOT_PATH") or "").strip()
    if raw:
        # Accept full URLs unchanged; normalise bare paths.
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw.rstrip("/")
        if not raw.startswith("/"):
            return f"/{raw}"
        return raw

    space_host = (os.environ.get("SPACE_HOST") or "").strip()
    if space_host:
        root = f"https://{space_host}"
        logger.info("HF Spaces detected — using root_path='%s'", root)
        return root

    return None


if __name__ == "__main__":
    _root_path = _resolve_gradio_root_path()
    logger.info("Gradio root_path resolved to: %s", _root_path)

    _demo.launch(
        server_name="0.0.0.0",
        server_port=settings.API_PORT,
        root_path="/",
        ssr_mode=False,
        show_error=True,
    )
