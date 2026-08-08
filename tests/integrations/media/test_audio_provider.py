"""Characterization tests for the OpenAI-compatible speech provider."""

import asyncio
import base64
from types import SimpleNamespace

import opensprite.integrations.media.audio as audio_module
from opensprite.integrations.media.audio import OpenAICompatibleSpeechProvider


def test_openai_compatible_speech_provider_preserves_request_contract(monkeypatch):
    client_kwargs = []
    requests = []

    class FakeTranscriptions:
        async def create(self, **kwargs):
            audio_file = kwargs["file"]
            requests.append(
                {
                    **kwargs,
                    "file": {
                        "name": audio_file.name,
                        "content": audio_file.read(),
                    },
                }
            )
            return SimpleNamespace(text="transcribed text")

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            client_kwargs.append(kwargs)
            self.audio = SimpleNamespace(transcriptions=FakeTranscriptions())

    monkeypatch.setattr(audio_module, "AsyncOpenAI", FakeAsyncOpenAI)
    provider = OpenAICompatibleSpeechProvider(
        api_key="speech-key",
        default_model="default-speech-model",
        base_url="https://speech.example.test/v1",
    )
    audio_data = base64.b64encode(b"audio-bytes").decode("ascii")

    result = asyncio.run(
        provider.transcribe(
            f"data:audio/ogg;base64,{audio_data}",
            model="request-model",
            language="zh",
        )
    )

    assert result == "transcribed text"
    assert client_kwargs == [
        {
            "api_key": "speech-key",
            "base_url": "https://speech.example.test/v1",
        }
    ]
    assert requests == [
        {
            "model": "request-model",
            "file": {"name": "audio.ogg", "content": b"audio-bytes"},
            "language": "zh",
        }
    ]


def test_openai_compatible_speech_provider_uses_defaults_and_empty_text(monkeypatch):
    client_kwargs = []
    requests = []

    class FakeTranscriptions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(text=None)

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            client_kwargs.append(kwargs)
            self.audio = SimpleNamespace(transcriptions=FakeTranscriptions())

    monkeypatch.setattr(audio_module, "AsyncOpenAI", FakeAsyncOpenAI)
    provider = OpenAICompatibleSpeechProvider(
        api_key="speech-key",
        default_model="default-speech-model",
    )
    audio_data = base64.b64encode(b"audio-bytes").decode("ascii")

    result = asyncio.run(provider.transcribe(f"data:audio/mpeg;base64,{audio_data}"))

    assert result == ""
    assert client_kwargs == [{"api_key": "speech-key"}]
    assert requests[0]["model"] == "default-speech-model"
    assert requests[0]["language"] is None
    assert requests[0]["file"].name == "audio.mpeg"
