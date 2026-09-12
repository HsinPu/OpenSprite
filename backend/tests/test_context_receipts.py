from dataclasses import replace
from uuid import uuid4

from opensprite_backend.agent.context.receipt import ReceiptSources, request_receipt
from opensprite_backend.agent.context.counter import ConservativeTokenCounter
from opensprite_backend.conversations.context_receipts import valid_context_receipt
from opensprite_backend.inference.models import ModelRequest, ModelMessage, ModelToolDefinition


def test_receipt_matches_gateway_input_without_double_counting_or_content():
    messages = (ModelMessage(role="system", content="secret system and skills"),
                ModelMessage(role="user", content="private historical text"),
                ModelMessage(role="user", content="current private request"))
    ids = [str(uuid4()), str(uuid4())]
    sources = ReceiptSources(bindings=((messages[1], "history", ids[0], 1), (messages[2], "currentUser", ids[1], 2)),
                             context_limit=8192, input_budget=6000)
    request = ModelRequest(provider_id="openai", model_id="test", response_mode="default", messages=messages,
                           tools=(ModelToolDefinition("lookup", "private description", {"type": "object"}),))
    receipt = request_receipt(request, sources, "main")
    assert valid_context_receipt(receipt)
    assert receipt["estimatedInputTokens"] == ConservativeTokenCounter().request(request.messages, request.tools)
    assert sum(receipt["components"].values()) == receipt["estimatedInputTokens"]
    assert receipt["historyMessageIds"] == ids
    assert all(text not in str(receipt) for text in ("secret", "private", "description"))
    changed = replace(request, tools=(ModelToolDefinition("lookup", "private description", {"type": "string"}),))
    assert request_receipt(changed, sources, "main")["requestHash"] != receipt["requestHash"]
    assert request_receipt(changed, sources, "main")["toolsHash"] != receipt["toolsHash"]
    assert request_receipt(request, sources, "main")["requestHash"] == receipt["requestHash"]
    assert not valid_context_receipt({**receipt, "prompt": "secret"})
    assert not valid_context_receipt({**receipt, "estimatedInputTokens": receipt["estimatedInputTokens"] + 1})


def test_unknown_provenance_is_not_invented():
    request = ModelRequest(provider_id="openai", model_id="test", response_mode="default",
                           messages=(ModelMessage(role="user", content="input"),), tools=())
    receipt = request_receipt(request, None, "main")
    assert valid_context_receipt(receipt)
    assert receipt["inputBudgetTokens"] is None
    assert receipt["historyMessageIds"] == []
    assert receipt["components"]["unattributed"] > 0
    assert receipt["components"]["currentUser"] == 0
