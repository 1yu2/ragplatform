from __future__ import annotations

from typing import Any

from app.core.config import get_settings


class OpenAICompatClient:
    """Unified OpenAI-compatible client wrapper for all model providers."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def _import_openai() -> Any:
        try:
            from openai import OpenAI
        except Exception as e:
            raise RuntimeError(f"openai package not available: {type(e).__name__}: {e}")
        return OpenAI

    def _build_client(self, *, base_url: str, api_key: str) -> Any:
        OpenAI = self._import_openai()
        if not api_key:
            raise RuntimeError("API key is empty")
        return OpenAI(base_url=base_url, api_key=api_key)

    def modelscope_client(self) -> Any:
        return self._build_client(
            base_url=self.settings.modelscope_base_url,
            api_key=self.settings.modelscope_api_key,
        )

    def openrouter_client(self) -> Any:
        return self._build_client(
            base_url=self.settings.openrouter_base_url,
            api_key=self.settings.openrouter_api_key,
        )

    # --- OpenAI-compatible call helpers ---
    def chat_completion_modelscope(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        client = self.modelscope_client()
        return client.chat.completions.create(
            model=self.settings.modelscope_llm_model,
            messages=messages,
            **kwargs,
        )

    def chat_completion_openrouter(self, messages: list[dict[str, Any]], model: str | None = None, **kwargs: Any) -> Any:
        client = self.openrouter_client()
        model_name = model or self.settings.openrouter_image_model
        return client.chat.completions.create(
            model=model_name,
            messages=messages,
            **kwargs,
        )

    def embedding_openrouter(self, input_data: Any, model: str | None = None, **kwargs: Any) -> Any:
        client = self.openrouter_client()
        model_name = model or self.settings.openrouter_embedding_model
        return client.embeddings.create(
            model=model_name,
            input=input_data,
            **kwargs,
        )
