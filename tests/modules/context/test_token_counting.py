from opensprite.core.contracts.llm import ChatMessage
from opensprite.modules.context.token_counting import (
    count_messages_tokens,
    count_text_tokens,
    estimate_text_tokens,
)


class _FakeEncoding:
    def encode(self, text: str) -> list[int]:
        return list(range(len(text.split())))


def test_estimate_text_tokens_handles_empty_and_mixed_text():
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("hello world") >= 2
    assert estimate_text_tokens("你好 world") >= 3


def test_count_text_tokens_uses_tiktoken_when_available(monkeypatch):
    monkeypatch.setattr(
        "opensprite.modules.context.token_counting._get_encoding",
        lambda **kwargs: _FakeEncoding(),
    )

    assert count_text_tokens("one two three") == 3


def test_count_messages_tokens_counts_serialized_messages(monkeypatch):
    monkeypatch.setattr(
        "opensprite.modules.context.token_counting.count_text_tokens",
        lambda text, **kwargs: len(text),
    )

    messages = [
        ChatMessage(role="system", content="hello"),
        ChatMessage(role="user", content=[{"type": "text", "text": "hi"}]),
    ]

    result = count_messages_tokens(messages)

    assert result > len("hello")
    assert result > len("hi")
