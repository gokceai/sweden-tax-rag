import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from dotenv import load_dotenv
import logging
from src.core.config import settings

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnswerGenerator:
    def __init__(self):
        self.model_path = settings.LLM_MODEL_PATH
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"The LLM engine is being started. Hardware being used.: {self.device.upper()}")
        logger.info(f"Target Model: {self.model_path}")
        logger.info("Model weights are being loaded into memory, please wait....")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        # RAM-optimized model loading.
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=torch.bfloat16, 
            low_cpu_mem_usage=True,     
            device_map="auto" if self.device == "cuda" else None
        )
        
        if self.device == "cpu":
            self.model.to(self.device)
            
        logger.info("The Llama 3.2 model has been successfully loaded and is ready for production!")

    def generate_answer(self, query: str, contexts: list) -> str:
        if not contexts:
            return settings.WARNING_PROMPT

        combined_context = "\n\n".join(contexts)
        prompt = settings.SYSTEM_PROMPT.format(context=combined_context, query=query)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=settings.LLM_MAX_NEW_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )

        input_length = inputs['input_ids'].shape[-1]
        response = self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
        return response.strip()

answer_generator = AnswerGenerator()
