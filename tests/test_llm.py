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


def test_generate_answer_with_context_uses_model(monkeypatch):
    generator = AnswerGenerator(settings)

    class FakeInputIds:
        shape = (1, 3)

    class FakeInputs(dict):
        def to(self, device):
            return self

    class FakeTokenizer:
        eos_token_id = 0

        def __call__(self, prompt, return_tensors):
            assert return_tensors == "pt"
            assert "QUESTION:" in prompt
            return FakeInputs({"input_ids": FakeInputIds()})

        def decode(self, tokens, skip_special_tokens):
            assert skip_special_tokens is True
            assert tokens == [4, 5, 6]
            return " mocked answer "

    class FakeModel:
        def generate(self, **kwargs):
            assert kwargs["max_new_tokens"] == settings.LLM_MAX_NEW_TOKENS
            assert kwargs["temperature"] == settings.LLM_TEMPERATURE
            assert kwargs["do_sample"] is True
            return [[1, 2, 3, 4, 5, 6]]

    generator.tokenizer = FakeTokenizer()
    generator.model = FakeModel()

    called = {"loaded": False}

    def _mark_loaded():
        called["loaded"] = True

    monkeypatch.setattr(generator, "_ensure_model_loaded", _mark_loaded)

    answer = generator.generate_answer("question", ["context text"])

    assert answer == "mocked answer"
    assert called["loaded"] is False
