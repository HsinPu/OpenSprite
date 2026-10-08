
from opensprite_backend.inference.models import ModelRequest, ModelMessage
from dataclasses import replace
from uuid import uuid4
import pytest
from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.inference.capabilities import ModelCapability

from opensprite_backend.agent.context.receipt import ReceiptSources, request_receipt
from opensprite_backend.agent.context.counter import ConservativeTokenCounter
from opensprite_backend.conversations.context_receipts import valid_context_receipt


def test_unknown_provenance_is_not_invented():
    request = ModelRequest(provider_id="openai", model_id="test", response_mode="default",
                           messages=(ModelMessage(role="user", content="input"),))
    receipt = request_receipt(request, None, "main")
    assert valid_context_receipt(receipt)
    assert receipt["inputBudgetTokens"] is None
    assert receipt["historyMessageIds"] == []
    assert receipt["components"]["unattributed"] > 0
    assert receipt["components"]["currentUser"] == 0
