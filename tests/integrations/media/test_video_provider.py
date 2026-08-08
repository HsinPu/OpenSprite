import asyncio
from types import SimpleNamespace

import opensprite.integrations.media.video as video_module


def test_openai_compatible_video_provider_builds_video_url_payload(monkeypatch):
    captured = {}
    client_kwargs = []

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="video analysis"))]
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            client_kwargs.append(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(video_module, "AsyncOpenAI", FakeAsyncOpenAI)

    provider = video_module.OpenAICompatibleVideoProvider(
        api_key="k",
        default_model="minimax-video",
        base_url="https://video.example.test/v1",
    )
    result = asyncio.run(provider.analyze("describe the clip", "data:video/mp4;base64,AAAA"))

    assert result == "video analysis"
    assert client_kwargs == [{"api_key": "k", "base_url": "https://video.example.test/v1"}]
    assert captured["model"] == "minimax-video"
    assert captured["messages"][0]["content"][0] == {"type": "text", "text": "describe the clip"}
    assert captured["messages"][0]["content"][1] == {
        "type": "video_url",
        "video_url": {"url": "data:video/mp4;base64,AAAA"},
    }


def test_openai_compatible_video_provider_preserves_optional_fields_and_empty_response(monkeypatch):
    captured = {}
    client_kwargs = []

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[])

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            client_kwargs.append(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(video_module, "AsyncOpenAI", FakeAsyncOpenAI)
    provider = video_module.OpenAICompatibleVideoProvider(api_key="k", default_model="default-video")

    result = asyncio.run(
        provider.analyze(
            "",
            "data:video/mp4;base64,AAAA",
            model="request-video",
            max_tokens=256,
        )
    )

    assert result == ""
    assert client_kwargs == [{"api_key": "k"}]
    assert captured == {
        "model": "request-video",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the provided video."},
                    {
                        "type": "video_url",
                        "video_url": {"url": "data:video/mp4;base64,AAAA"},
                    },
                ],
            }
        ],
        "max_tokens": 256,
    }
