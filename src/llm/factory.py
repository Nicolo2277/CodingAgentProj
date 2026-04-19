from __future__ import annotations

from src.config import DEFAULT_PROVIDER, MODELS
from src.llm.client import BaseLLMClient, OllamaClient, OpenAIClient, AnthropicClient

_CLIENTS: dict[str, type[BaseLLMClient]] = {
    "ollama":    OllamaClient,
    "openai":    OpenAIClient,
    "anthropic": AnthropicClient,
}


def get_client(
    provider: str = DEFAULT_PROVIDER,
    model: str | None = None,
) -> BaseLLMClient:
    if provider not in _CLIENTS:
        raise ValueError(f"Provider not supported: {provider}")

    return _CLIENTS[provider](model=model or MODELS[provider])