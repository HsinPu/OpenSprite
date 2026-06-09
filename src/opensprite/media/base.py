"""Media provider interfaces for OpenSprite."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ImageAnalysisProvider(ABC):
    """Provider interface for image understanding."""

    @abstractmethod
    async def analyze(
        self,
        instruction: str,
        images: list[str],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Analyze one or more images and return a text result."""
        raise NotImplementedError


class SpeechToTextProvider(ABC):
    """Provider interface for audio transcription."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data_url: str,
        *,
        model: str | None = None,
        language: str | None = None,
    ) -> str:
        """Transcribe one audio payload and return text."""
        raise NotImplementedError


class VideoAnalysisProvider(ABC):
    """Provider interface for video understanding."""

    @abstractmethod
    async def analyze(
        self,
        instruction: str,
        video_data_url: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Analyze one video payload and return text."""
        raise NotImplementedError
