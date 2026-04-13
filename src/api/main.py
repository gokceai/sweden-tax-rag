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
    _root_path: str | None = None
    if os.environ.get("SYSTEM") == "spaces":
        _space_id = os.environ.get("SPACE_ID", "")
        if "/" in _space_id:
            _author, _repo = _space_id.split("/", 1)
            _root_path = f"https://{_author.lower()}-{_repo.lower()}.hf.space"

    _demo.launch(
        server_name="0.0.0.0",
        server_port=settings.API_PORT,
        root_path=_root_path,
        ssr_mode=False,
        show_api=False,
    )
