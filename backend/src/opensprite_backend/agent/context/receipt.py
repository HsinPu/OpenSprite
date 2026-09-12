"""Safe receipts of normalized gateway inputs, never full prompt storage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from opensprite_backend.inference.models import ModelMessage, ModelRequest
from .counter import ConservativeTokenCounter


def content_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReceiptSources:
    # Object identity binds metadata to the exact immutable selected message.
    bindings: tuple[tuple[ModelMessage, str, str, int], ...] = ()
    summary: dict[str, object] | None = None
    skills: tuple[dict[str, object], ...] = ()
    workspace: dict[str, object] | None = None
    context_limit: int | None = None
    input_budget: int | None = None
    history_ids: tuple[str, ...] = ()


def request_receipt(request: ModelRequest, sources: ReceiptSources | None, purpose: str) -> dict[str, object]:
    counter = ConservativeTokenCounter()
    sources = sources or ReceiptSources()
    components = dict.fromkeys(("system", "summary", "history", "currentUser", "toolResults", "assistant", "summaryInput", "unattributed", "toolDefinitions", "framing"), 0)
    bindings = {id(message): (kind, identifier, sequence) for message, kind, identifier, sequence in sources.bindings}
    history_ids = list(sources.history_ids)
    for message in request.messages:
        binding = bindings.get(id(message))
        if message.role == "system":
            kind = "system"
        elif purpose == "compaction":
            kind = "summaryInput"
        elif binding is not None:
            kind = binding[0]
            if kind in ("history", "currentUser"):
                history_ids.append(binding[1])
        else:
            kind = "toolResults" if message.role == "tool" else "assistant" if message.role == "assistant" else "unattributed"
        components[kind] += counter.message(message)
    components["toolDefinitions"] = sum(counter.tool(tool) for tool in request.tools)
    components["framing"] = 3
    normalized = {
        "providerId": request.provider_id, "modelId": request.model_id,
        "responseMode": request.response_mode, "maxOutputTokens": request.max_output_tokens,
        "messages": [asdict(message) for message in request.messages],
        "tools": [asdict(tool) for tool in request.tools],
    }
    return {
        "schemaVersion": 1, "requestHash": content_hash(normalized),
        "estimateMethod": "utf8-conservative-v1", "estimatedInputTokens": sum(components.values()),
        "components": components, "contextLimitTokens": sources.context_limit,
        "inputBudgetTokens": sources.input_budget, "outputReserveTokens": request.max_output_tokens,
        "messageCount": len(request.messages), "toolCount": len(request.tools),
        "systemHash": content_hash([asdict(message) for message in request.messages if message.role == "system"]),
        "toolsHash": content_hash(normalized["tools"]),
        "historyMessageIds": history_ids, "summary": sources.summary,
        "skills": list(sources.skills), "workspace": sources.workspace,
    }
