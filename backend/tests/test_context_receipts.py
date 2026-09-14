from dataclasses import replace
from uuid import uuid4
import pytest
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.inference.capabilities import ModelCapability

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


@pytest.mark.parametrize("enabled,model_tools,has_tools,compat,policy,transport", [
    (True, True, True, True, "inherit", "non_streaming"),
    (True, True, True, False, "inherit", "streaming"),
    (True, True, False, True, "inherit", "streaming"),
    (False, False, False, True, "provider_disabled", "streaming"),
    (True, False, False, True, "model_disabled", "streaming"),
])
def test_tool_execution_receipt_and_legacy_validation(enabled, model_tools, has_tools, compat, policy, transport):
    pid = str(uuid4())
    endpoint = ProviderEndpointSnapshot(pid, 1, "openai_chat_completions", "https://example.com/v1", "none",
        (ModelCapability(pid, "test", "Test", 8192, 2048, model_tools),), compat, enabled)
    request = ModelRequest(pid, "test", "default", (ModelMessage("user", "synthetic"),),
        (ModelToolDefinition("calculator", "Calculate", {"type": "object"}),) if has_tools else (), provider_endpoint=endpoint)
    receipt = request_receipt(request, None, "main")
    assert receipt["toolExecution"] == {"policy": policy, "transport": transport}
    assert valid_context_receipt(receipt)
    assert not valid_context_receipt({**receipt, "toolExecution": {"policy": "invented", "transport": transport}})
    del receipt["toolExecution"]
    assert valid_context_receipt(receipt)
