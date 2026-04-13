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
    # Gradio embeds root_path as window.gradio_config.root in the page HTML.
    # The browser JS uses this URL for all API/WebSocket calls.
    # Without a correct public URL the JS calls http://0.0.0.0:7860 →
    # network error → blank page.
    #
    # Priority: GRADIO_ROOT_PATH env var (set by entrypoint.sh) →
    #           SPACE_HOST env var → SPACE_ID derivation → None (local dev).
    _root_path: str | None = (
        os.environ.get("GRADIO_ROOT_PATH")
        or (f"https://{os.environ['SPACE_HOST']}" if os.environ.get("SPACE_HOST") else None)
        or (
            "https://{}-{}.hf.space".format(
                *[p.lower().replace("_", "-") for p in os.environ["SPACE_ID"].split("/", 1)]
            )
            if os.environ.get("SPACE_ID", "").count("/") >= 1
            else None
        )
    )
    logger.info("Gradio root_path resolved to: %s", _root_path)

    _demo.launch(
        server_name="0.0.0.0",
        server_port=settings.API_PORT,
        root_path=_root_path,
        ssr_mode=False,
    )
