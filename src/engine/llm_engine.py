import threading
import logging

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class AnswerGenerator:
    def __init__(self, settings):
        ...
        self.tokenizer = None
        self.model = None
        ...

    def _ensure_model_loaded(self) -> None:
        ...
        self.model = self._load_model()
        self.model.eval()
        ...

    def generate_answer(self, query: str, contexts: list) -> str:
        if not contexts:
            return self.settings.WARNING_PROMPT
        if not self.is_ready:
            self._ensure_model_loaded()

        trimmed_contexts = contexts[: self.settings.MAX_CONTEXT_CHUNKS]
        combined_context = "\n\n".join(trimmed_contexts)
        if len(combined_context) > self.settings.MAX_CONTEXT_CHARS:
            combined_context = combined_context[: self.settings.MAX_CONTEXT_CHARS]

        prompt = self.settings.SYSTEM_PROMPT.format(context=combined_context, query=query)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.settings.LLM_MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
                use_cache=True,
                repetition_penalty=1.05,
            )

        input_length = inputs["input_ids"].shape[-1]
        return self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()