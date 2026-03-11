from __future__ import annotations

import logging
import os
from enum import Enum
from importlib.util import find_spec
from typing import Any, Literal

import requests

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None  # type: ignore[assignment]
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


BackendType = Literal["openai", "ollama", "huggingface", "fallback"]


class LLMBackend(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"
    FALLBACK = "fallback"


class UnifiedLLMClient:
    """
    Unified local LLM client.
    Priority: Ollama -> HuggingFace transformers -> OpenAI -> structured fallback text.
    """

    def __init__(self) -> None:
        self.backend: LLMBackend = LLMBackend.FALLBACK
        self.openai_client: Any | None = None
        self.openai_api_key: str | None = None
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3:mini")
        self.hf_model_name = os.getenv("HF_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")

        self.hf_model: Any | None = None
        self.hf_tokenizer: Any | None = None
        self.hf_device: str | None = None

        self.refresh_backend()

    def refresh_backend(self, force_backend: BackendType | None = None) -> None:
        """
        Re-run backend detection.
        Useful when backend services are started after API process boot.
        """
        if force_backend is not None:
            selected = LLMBackend(force_backend)
            if self._is_backend_available(selected):
                self.backend = selected
                logger.info("LLM backend forced to: %s", selected.value)
            else:
                self.backend = LLMBackend.FALLBACK
                logger.warning("Requested backend unavailable: %s. Falling back.", selected.value)
            return

        if self._check_ollama():
            self.backend = LLMBackend.OLLAMA
            logger.info("LLM backend selected: ollama")
            return

        if self._check_huggingface():
            self.backend = LLMBackend.HUGGINGFACE
            logger.info("LLM backend selected: huggingface")
            return

        if self._check_openai():
            self.backend = LLMBackend.OPENAI
            logger.info("LLM backend selected: openai")
            return

        self.backend = LLMBackend.FALLBACK
        logger.warning("No LLM backend available. Using fallback summaries.")

    def _is_backend_available(self, backend: LLMBackend) -> bool:
        if backend == LLMBackend.OPENAI:
            return self._check_openai()
        if backend == LLMBackend.OLLAMA:
            return self._check_ollama()
        if backend == LLMBackend.HUGGINGFACE:
            return self._check_huggingface()
        return True

    def _check_openai(self) -> bool:
        if not OPENAI_AVAILABLE:
            return False

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            self.openai_client = None
            self.openai_api_key = None
            return False

        if self.openai_client is not None and self.openai_api_key == api_key:
            return True

        try:
            self.openai_client = OpenAI(api_key=api_key)
            self.openai_api_key = api_key
            return True
        except Exception as exc:
            logger.error("OpenAI client init failed: %s", exc)
            self.openai_client = None
            self.openai_api_key = None
            return False

    def _check_ollama(self) -> bool:
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3:mini")
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def _check_huggingface(self) -> bool:
        self.hf_model_name = os.getenv("HF_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
        return find_spec("transformers") is not None and find_spec("torch") is not None

    def _has_gpu(self) -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _get_ollama_models(self) -> list[str]:
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models", [])
            names = []
            for model in models:
                if isinstance(model, dict):
                    name = str(model.get("name", "")).strip()
                    if name:
                        names.append(name)
            if names:
                return names
        except Exception:
            pass
        return [self.ollama_model]

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

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 320,
        force_backend: BackendType | None = None,
        force_model: str | None = None,
    ) -> str:
        if force_backend is not None:
            requested_backend = LLMBackend(force_backend)
            if not self._is_backend_available(requested_backend):
                raise ValueError(f"{requested_backend.value} backend is not available.")
            try:
                text = self._generate_with_backend(
                    requested_backend,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model_override=force_model,
                )
            except Exception as exc:
                # Forced backend selection should never take down report generation.
                logger.error("Forced %s generation failed: %s", requested_backend.value, exc)
                self.backend = LLMBackend.FALLBACK
                return self._generate_fallback(prompt)
            if text:
                return text
            self.backend = LLMBackend.FALLBACK
            return self._generate_fallback(prompt)

        if self.backend == LLMBackend.OLLAMA:
            text = self._generate_ollama(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=force_model,
            )
            if text:
                return text
            if self._check_huggingface():
                self.backend = LLMBackend.HUGGINGFACE
            elif self._check_openai():
                self.backend = LLMBackend.OPENAI
            else:
                self.backend = LLMBackend.FALLBACK

        if self.backend == LLMBackend.HUGGINGFACE:
            text = self._generate_huggingface(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=force_model,
            )
            if text:
                return text
            if self._check_openai():
                self.backend = LLMBackend.OPENAI
            else:
                self.backend = LLMBackend.FALLBACK

        if self.backend == LLMBackend.OPENAI:
            try:
                text = self._generate_openai(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model_override=force_model,
                )
                if text:
                    return text
            except Exception as exc:
                logger.error("OpenAI generation failed: %s", exc)
            self.backend = LLMBackend.FALLBACK

        return self._generate_fallback(prompt)

    def _generate_with_backend(
        self,
        backend: LLMBackend,
        prompt: str,
        temperature: float,
        max_tokens: int,
        model_override: str | None = None,
    ) -> str | None:
        if backend == LLMBackend.OPENAI:
            return self._generate_openai(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=model_override,
            )
        if backend == LLMBackend.OLLAMA:
            return self._generate_ollama(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=model_override,
            )
        if backend == LLMBackend.HUGGINGFACE:
            return self._generate_huggingface(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=model_override,
            )
        return self._generate_fallback(prompt)

    def _generate_openai(
        self, prompt: str, temperature: float, max_tokens: int, model_override: str | None = None
    ) -> str:
        if self.openai_client is None and not self._check_openai():
            raise ValueError("OpenAI is not configured. Set OPENAI_API_KEY in .env")

        selected_model = model_override or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        env_max_tokens = os.getenv("OPENAI_MAX_TOKENS")
        env_temperature = os.getenv("OPENAI_TEMPERATURE")
        final_max_tokens = max_tokens
        final_temperature = temperature

        if env_max_tokens:
            try:
                final_max_tokens = int(env_max_tokens)
            except ValueError:
                logger.warning("Invalid OPENAI_MAX_TOKENS=%s. Using %s.", env_max_tokens, max_tokens)

        if env_temperature:
            try:
                final_temperature = float(env_temperature)
            except ValueError:
                logger.warning("Invalid OPENAI_TEMPERATURE=%s. Using %s.", env_temperature, temperature)

        response = self.openai_client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": "You are an energy market analyst."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=final_max_tokens,
            temperature=final_temperature,
            timeout=60,
        )
        content = response.choices[0].message.content
        return (content or "").strip()

    def _generate_ollama(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        model_override: str | None = None,
    ) -> str | None:
        selected_model = model_override or self.ollama_model
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": selected_model,
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

    def _generate_huggingface(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        model_override: str | None = None,
    ) -> str | None:
        if model_override and model_override != self.hf_model_name:
            self.hf_model_name = model_override
            self.hf_model = None
            self.hf_tokenizer = None
            self.hf_device = None
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
            "3. OpenAI path: set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`\n"
            f"Active backend: {self.backend.value}"
        )

    def get_available_backends(self) -> dict[BackendType, bool]:
        return {
            "openai": self._check_openai(),
            "ollama": self._check_ollama(),
            "huggingface": self._check_huggingface(),
            "fallback": True,
        }

    def get_backend_info(self) -> dict[str, Any]:
        available = self.get_available_backends()
        backend = self.backend.value

        if not available.get(backend, False):
            self.refresh_backend()
            backend = self.backend.value

        backend_entries: list[dict[str, Any]] = []
        available_names: list[str] = []

        if available["ollama"]:
            models = self._get_ollama_models()
            backend_entries.append(
                {
                    "type": LLMBackend.OLLAMA.value,
                    "models": models,
                    "url": self.ollama_url,
                }
            )
            available_names.append(LLMBackend.OLLAMA.value)

        if available["huggingface"]:
            backend_entries.append(
                {
                    "type": LLMBackend.HUGGINGFACE.value,
                    "models": [self.hf_model_name],
                    "device": "cuda" if self._has_gpu() else "cpu",
                }
            )
            available_names.append(LLMBackend.HUGGINGFACE.value)

        if available["openai"]:
            backend_entries.append(
                {
                    "type": LLMBackend.OPENAI.value,
                    "models": [self.openai_model],
                }
            )
            available_names.append(LLMBackend.OPENAI.value)

        backend_entries.append(
            {
                "type": LLMBackend.FALLBACK.value,
                "models": ["template"],
            }
        )
        available_names.append(LLMBackend.FALLBACK.value)

        return {
            "backend": backend,
            "active_backend": backend,
            "available_backends": backend_entries,
            "available_backend_types": available_names,
            "openai_model": self.openai_model if available["openai"] else None,
            "ollama_url": self.ollama_url if available["ollama"] else None,
            "ollama_model": self._get_ollama_models()[0] if available["ollama"] else None,
            "hf_model": self.hf_model_name if available["huggingface"] else None,
            "hf_device": self.hf_device if backend == LLMBackend.HUGGINGFACE.value else None,
        }


_llm_client: UnifiedLLMClient | None = None


def get_llm() -> UnifiedLLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = UnifiedLLMClient()
    return _llm_client
