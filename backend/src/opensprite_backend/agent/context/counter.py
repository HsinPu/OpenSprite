"""Conservative local token estimates for provider-neutral preflight checks."""

from __future__ import annotations

import json

from opensprite_backend.inference.models import ModelMessage, ModelToolDefinition


class ConservativeTokenCounter:
    """Estimate high enough for mixed English, CJK, JSON, and tool metadata."""

    @staticmethod
    def text(text: str) -> int:
        encoded_bytes = len(text.encode("utf-8"))
        return max(1, (encoded_bytes + 2) // 3)

    def message(self, message: ModelMessage) -> int:
        tokens = 6 + self.text(message.role) + self.text(message.content)
        if message.tool_call_id is not None:
            tokens += self.text(message.tool_call_id)
        if message.tool_name is not None:
            tokens += self.text(message.tool_name)
        for call in message.tool_calls:
            tokens += 8 + self.text(call.call_id) + self.text(call.name)
            tokens += self.text(
                json.dumps(
                    call.arguments,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
        return tokens

    def tool(self, tool: ModelToolDefinition) -> int:
        encoded_schema = json.dumps(
            tool.input_schema,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return 12 + self.text(tool.name) + self.text(tool.description) + self.text(encoded_schema)

    def request(
        self,
        messages: tuple[ModelMessage, ...],
        tools: tuple[ModelToolDefinition, ...],
    ) -> int:
        return 3 + sum(self.message(message) for message in messages) + sum(
            self.tool(tool) for tool in tools
        )
