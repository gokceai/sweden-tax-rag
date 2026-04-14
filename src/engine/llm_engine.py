import logging
import threading

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.core.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class AnswerGenerator:
    def __init__(self, settings):
        self.settings = settings
        self.model_path = settings.LLM_MODEL_PATH
        self.device = settings.resolve_device(settings.LLM_DEVICE)
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.use_int8 = settings.LLM_USE_INT8

        if self.device != "cuda":
            logger.warning(
                "No GPU detected - LLM will run on CPU (dtype=%s, slower). Model: %s",
                self.dtype,
                self.model_path,
            )

        self.tokenizer = None
        self.model = None
        self._load_lock = threading.Lock()
        self._load_error: Exception | None = None

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    @property
    def has_error(self) -> bool:
        return self._load_error is not None

    def load(self) -> None:
        self._ensure_model_loaded()

    def _ensure_model_loaded(self) -> None:
        if self.is_ready:
            return

        with self._load_lock:
            if self.is_ready:
                return
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token

                self.model = self._load_model()
                if self.device == "cpu":
                    self.model.to(self.device)
                self.model.eval()

                logger.info("LLM '%s' loaded on %s.", self.model_path, self.device.upper())
            except Exception as e:
                self._load_error = e
                raise InfrastructureError(f"LLM load failed: {e}") from e

    def _load_model(self):
        if self.device == "cuda" and self.use_int8:
            try:
                from transformers import BitsAndBytesConfig  # noqa: PLC0415

                logger.info("Loading LLM with GPU 8-bit quantization (bitsandbytes).")
                return AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    quantization_config=BitsAndBytesConfig(load_in_8bit=True),
                    low_cpu_mem_usage=True,
                    device_map="auto",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("INT8 GPU quantization unavailable; falling back to dtype load: %s", exc)

        model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=self.dtype,
            low_cpu_mem_usage=True,
            device_map="auto" if self.device == "cuda" else None,
        )

        if self.device == "cpu" and self.use_int8:
            try:
                logger.info("Applying dynamic INT8 quantization on CPU.")
                model = torch.quantization.quantize_dynamic(
                    model,
                    {torch.nn.Linear},
                    dtype=torch.qint8,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("CPU INT8 quantization failed; using non-quantized model: %s", exc)

        return model

    def generate_answer(self, query: str, contexts: list[str]) -> str:
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