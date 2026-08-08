import asyncio
import inspect

import pytest

from opensprite.core.ports.media import (
    ImageAnalysisProvider,
    SpeechToTextProvider,
    VideoAnalysisProvider,
)


class FakeImageAnalysisProvider(ImageAnalysisProvider):
    async def analyze(
        self,
        instruction: str,
        images: list[str],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return f"{instruction}:{','.join(images)}:{model}:{max_tokens}"


class FakeSpeechToTextProvider(SpeechToTextProvider):
    async def transcribe(
        self,
        audio_data_url: str,
        *,
        model: str | None = None,
        language: str | None = None,
    ) -> str:
        return f"{audio_data_url}:{model}:{language}"


class FakeVideoAnalysisProvider(VideoAnalysisProvider):
    async def analyze(
        self,
        instruction: str,
        video_data_url: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return f"{instruction}:{video_data_url}:{model}:{max_tokens}"


def test_media_provider_ports_remain_abstract():
    for provider_type in (ImageAnalysisProvider, SpeechToTextProvider, VideoAnalysisProvider):
        with pytest.raises(TypeError):
            provider_type()


def test_media_provider_ports_preserve_method_signatures():
    signatures = {
        ImageAnalysisProvider.analyze: (
            ("self", "instruction", "images", "model", "max_tokens"),
            {"model", "max_tokens"},
        ),
        SpeechToTextProvider.transcribe: (
            ("self", "audio_data_url", "model", "language"),
            {"model", "language"},
        ),
        VideoAnalysisProvider.analyze: (
            ("self", "instruction", "video_data_url", "model", "max_tokens"),
            {"model", "max_tokens"},
        ),
    }

    for method, (expected_names, keyword_only_names) in signatures.items():
        assert inspect.iscoroutinefunction(method)
        parameters = inspect.signature(method).parameters
        assert tuple(parameters) == expected_names
        for name in keyword_only_names:
            assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
            assert parameters[name].default is None


def test_media_provider_ports_preserve_async_call_contracts():
    async def scenario():
        image_result = await FakeImageAnalysisProvider().analyze(
            "inspect", ["image-a"], model="vision", max_tokens=100
        )
        speech_result = await FakeSpeechToTextProvider().transcribe(
            "audio-a", model="speech", language="zh-TW"
        )
        video_result = await FakeVideoAnalysisProvider().analyze(
            "inspect", "video-a", model="video", max_tokens=200
        )
        return image_result, speech_result, video_result

    assert asyncio.run(scenario()) == (
        "inspect:image-a:vision:100",
        "audio-a:speech:zh-TW",
        "inspect:video-a:video:200",
    )
