"""Conservative local token estimates for provider-neutral preflight checks."""

from __future__ import annotations

from opensprite_backend.agent.plugin import ModelMessage


class ConservativeTokenCounter:
    """Estimate high enough for mixed English, CJK, and JSON."""

    @staticmethod
    def text(text: str) -> int:
        encoded_bytes = len(text.encode("utf-8"))
        return max(1, (encoded_bytes + 2) // 3)

    def message(self, message: ModelMessage) -> int:
        return 6 + self.text(message.role) + self.text(message.content)

    def request(self, messages: tuple[ModelMessage, ...]) -> int:
        return 3 + sum(self.message(message) for message in messages)
