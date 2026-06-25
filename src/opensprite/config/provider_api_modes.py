"""Shared LLM provider API mode identifiers."""

from typing import Literal

CHAT_COMPLETIONS_API_MODE = "chat_completions"
RESPONSES_API_MODE = "responses"
ANTHROPIC_MESSAGES_API_MODE = "anthropic_messages"

ProviderApiMode = Literal[
    CHAT_COMPLETIONS_API_MODE,
    RESPONSES_API_MODE,
    ANTHROPIC_MESSAGES_API_MODE,
]
