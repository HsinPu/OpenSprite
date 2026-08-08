"""OpenAI-compatible speech-to-text provider."""

from __future__ import annotations

import base64
from io import BytesIO

from openai import AsyncOpenAI

from ...core.ports.media import SpeechToTextProvider


class OpenAICompatibleSpeechProvider(SpeechToTextProvider):
    """Speech-to-text provider backed by an OpenAI-compatible audio API."""

    def __init__(self, *, api_key: str, default_model: str, base_url: str | None = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)
        self.default_model = default_model

    async def transcribe(
        self,
        audio_data_url: str,
        *,
        model: str | None = None,
        language: str | None = None,
    ) -> str:
        header, encoded = audio_data_url.split(",", 1)
        mime_type = header.split(";", 1)[0].removeprefix("data:") or "audio/ogg"
        extension = mime_type.split("/")[-1] or "ogg"
        buffer = BytesIO(base64.b64decode(encoded))
        buffer.name = f"audio.{extension}"

        response = await self.client.audio.transcriptions.create(
            model=model or self.default_model,
            file=buffer,
            language=language,
        )
        return getattr(response, "text", "") or ""
