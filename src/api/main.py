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
    raw = (os.environ.get("GRADIO_ROOT_PATH") or "").strip()
    if raw:
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw.rstrip("/")
        if not raw.startswith("/"):
            return f"/{raw}"
        return raw
    return None


if __name__ == "__main__":
    _root_path = _resolve_gradio_root_path()
    logger.info("Gradio root_path resolved to: %s", _root_path)

    _demo.launch(
        server_name="0.0.0.0",
        server_port=settings.API_PORT,
        root_path=_root_path, 
        ssr_mode=True,
        show_error=True,
)
