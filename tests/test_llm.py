from src.core.config import settings
from src.engine.llm_engine import AnswerGenerator


def test_generate_answer_without_context_does_not_load_model(monkeypatch):
    generator = AnswerGenerator(settings)

    called = {"loaded": False}

    def _mark_loaded():
        called["loaded"] = True

    monkeypatch.setattr(generator, "_ensure_model_loaded", _mark_loaded)

    answer = generator.generate_answer("question", [])

    assert answer == settings.WARNING_PROMPT
    assert called["loaded"] is False
