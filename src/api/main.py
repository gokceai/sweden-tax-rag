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

if __name__ == "__main__":
    # HF Spaces injects SPACE_HOST as the exact public subdomain,
    # e.g. "owner-spacename.hf.space".  We need this so that Gradio puts
    # the correct URL in window.gradio_config.root — otherwise the browser
    # JS tries to reach the internal http://0.0.0.0:7860 address and the
    # page renders blank.
    _root_path: str | None = None
    _space_host = os.environ.get("SPACE_HOST", "")
    if _space_host:
        _root_path = f"https://{_space_host}"

    _demo.launch(
        server_name="0.0.0.0",
        server_port=settings.API_PORT,
        root_path=_root_path,
        ssr_mode=False,
    )
