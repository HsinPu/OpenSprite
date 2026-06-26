"""Shared helpers for providers backed by the OpenAI-compatible SDK."""

from __future__ import annotations

from typing import Any


class OpenAICompatibleClientMixin:
    """Mixin for providers that rebuild an AsyncOpenAI client from kwargs."""

    _client_kwargs: dict[str, Any]

    def _build_client(self) -> Any:
        from openai import AsyncOpenAI

        return AsyncOpenAI(**self._client_kwargs)

    def recover_after_error(self, error: BaseException) -> bool:
        _ = error
        try:
            self.client = self._build_client()
            return True
        except Exception:
            return False
