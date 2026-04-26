from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests

from src.config import OLLAMA_BASE_URL
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    duration_ms: int

    def as_json(self) -> dict:
        try:
            return json.loads(self.content)
        except json.JSONDecodeError as e:
            logger.error("Risposta non è JSON valido: %s", e)
            raise


class BaseLLMClient(ABC):
    def __init__(self, model: str):
        self.model = model
        logger.info("%s initialized — model=%s", self.__class__.__name__, model)

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        logger.debug("Prompt (first 200 char): %s", prompt[:200])
        response = self._complete(prompt, system, json_mode)
        logger.debug("Response received in %dms", response.duration_ms)
        return response

    @abstractmethod
    def _complete(
        self,
        prompt: str,
        system: Optional[str],
        json_mode: bool,
    ) -> LLMResponse:
        ...


class OllamaClient(BaseLLMClient):
    def __init__(self, model: str = "qwen2.5-coder:3b"):
        super().__init__(model)
        self.base_url = OLLAMA_BASE_URL

    def _complete(self, prompt, system, json_mode) -> LLMResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            **({"system": system} if system else {}),
            **({"format": "json"} if json_mode else {}),
        }

        start = time.time()
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.error("Impossible connection to Ollama on %s", self.base_url)
            raise
        except requests.exceptions.Timeout:
            logger.error("Timeout 120 seconds")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(" HTTP Error: %s — %s", e, e.response.text)
            raise

        data = response.json()
        return LLMResponse(
            content=data["response"],
            model=self.model,
            provider="ollama",
            duration_ms=int((time.time() - start) * 1000),
        )


class OpenAIClient(BaseLLMClient):
    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model)
        import os
        self.api_key = os.getenv("OPENAI_API_KEY")

    def _complete(self, prompt, system, json_mode) -> LLMResponse:

        raise NotImplementedError("OpenAIClient not yet implemented")


class AnthropicClient(BaseLLMClient):
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        super().__init__(model)
        import os
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def _complete(self, prompt, system, json_mode) -> LLMResponse:

        raise NotImplementedError("AnthropicClient not yet implemented")