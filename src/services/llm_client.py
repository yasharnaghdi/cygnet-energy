from __future__ import annotations

import logging
import os
from enum import Enum
from importlib.util import find_spec
from typing import Any

import requests

logger = logging.getLogger(__name__)


class LLMBackend(str, Enum):
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    FALLBACK = "fallback"


class UnifiedLLMClient:
    """
    Unified local LLM client.
    Priority: Ollama -> HuggingFace transformers -> structured fallback text.
    """

    def __init__(self) -> None:
        self.backend: LLMBackend = LLMBackend.FALLBACK
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama2:7b")
        self.hf_model_name = os.getenv("HF_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")

        self.hf_model: Any | None = None
        self.hf_tokenizer: Any | None = None
        self.hf_device: str | None = None

        self._detect_backend()

    def _detect_backend(self) -> None:
        if self._check_ollama():
            self.backend = LLMBackend.OLLAMA
            logger.info("LLM backend selected: ollama")
            return

        if self._check_huggingface():
            self.backend = LLMBackend.HUGGINGFACE
            logger.info("LLM backend selected: huggingface")
            return

        self.backend = LLMBackend.FALLBACK
        logger.warning("No local LLM backend available. Using fallback summaries.")

    def _check_ollama(self) -> bool:
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = {str(model.get("name", "")) for model in models if isinstance(model, dict)}
            return self.ollama_model in names or any(name.startswith(f"{self.ollama_model}:") for name in names)
        except Exception:
            return False

    def _check_huggingface(self) -> bool:
        return find_spec("transformers") is not None and find_spec("torch") is not None

    def _load_hf_model(self) -> None:
        if self.hf_model is not None and self.hf_tokenizer is not None:
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading HuggingFace model %s on %s", self.hf_model_name, device)

            self.hf_tokenizer = AutoTokenizer.from_pretrained(self.hf_model_name)
            self.hf_model = AutoModelForCausalLM.from_pretrained(
                self.hf_model_name,
                device_map="auto" if device == "cuda" else None,
                torch_dtype="auto",
                low_cpu_mem_usage=True,
            )
            if device == "cpu":
                self.hf_model = self.hf_model.to("cpu")
            self.hf_device = device
        except Exception as exc:
            logger.error("Failed to load HuggingFace model: %s", exc)
            self.hf_model = None
            self.hf_tokenizer = None
            self.hf_device = None
            self.backend = LLMBackend.FALLBACK

    def refresh_backend(self) -> None:
        """
        Re-run backend detection.
        Useful when Ollama is started after API process boot.
        """
        self._detect_backend()

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 320) -> str:
        if self.backend == LLMBackend.OLLAMA:
            text = self._generate_ollama(prompt, temperature=temperature, max_tokens=max_tokens)
            if text:
                return text
            if self._check_huggingface():
                self.backend = LLMBackend.HUGGINGFACE
            else:
                self.backend = LLMBackend.FALLBACK

        if self.backend == LLMBackend.HUGGINGFACE:
            text = self._generate_huggingface(prompt, temperature=temperature, max_tokens=max_tokens)
            if text:
                return text
            self.backend = LLMBackend.FALLBACK

        return self._generate_fallback(prompt)

    def _generate_ollama(self, prompt: str, temperature: float, max_tokens: int) -> str | None:
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=180,
            )
            response.raise_for_status()
            text = str(response.json().get("response", "")).strip()
            return text or None
        except Exception as exc:
            logger.error("Ollama generation failed: %s", exc)
            return None

    def _generate_huggingface(self, prompt: str, temperature: float, max_tokens: int) -> str | None:
        self._load_hf_model()
        if self.hf_model is None or self.hf_tokenizer is None:
            return None

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            inputs = self.hf_tokenizer(prompt, return_tensors="pt")
            inputs = {key: value.to(device) for key, value in inputs.items()}

            output = self.hf_model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.hf_tokenizer.eos_token_id,
            )

            prompt_len = inputs["input_ids"].shape[1]
            generated_ids = output[0][prompt_len:]
            text = self.hf_tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
            return text or None
        except Exception as exc:
            logger.error("HuggingFace generation failed: %s", exc)
            return None

    def _generate_fallback(self, prompt: str) -> str:
        extracted: list[str] = []
        for line in prompt.splitlines():
            if ":" not in line:
                continue
            if any(token in line for token in ("MW", "%", "EUR", "gCO2", "hours")):
                extracted.append(f"- {line.strip()}")

        points = "\n".join(extracted[:8]) if extracted else "- No quantitative metrics were parsed from prompt."
        return (
            "[AI narrative unavailable. Structured summary mode]\n\n"
            "Key data points:\n"
            f"{points}\n\n"
            "Enable a local model:\n"
            "1. Ollama path: install Ollama, pull a model, run `ollama serve`\n"
            "2. HuggingFace path: `poetry install --extras llm`\n"
            f"Active backend: {self.backend.value}"
        )

    def get_backend_info(self) -> dict[str, Any]:
        return {
            "backend": self.backend.value,
            "ollama_url": self.ollama_url if self.backend == LLMBackend.OLLAMA else None,
            "ollama_model": self.ollama_model if self.backend == LLMBackend.OLLAMA else None,
            "hf_model": self.hf_model_name if self.backend == LLMBackend.HUGGINGFACE else None,
            "hf_device": self.hf_device if self.backend == LLMBackend.HUGGINGFACE else None,
        }


_llm_client: UnifiedLLMClient | None = None


def get_llm() -> UnifiedLLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = UnifiedLLMClient()
    return _llm_client
