import pytest
from pydantic import ValidationError

from opensprite_backend.api.custom_provider_models import ProviderCreateRequest, ProviderUpdateRequest


def test_secret_is_not_serialized_or_represented():
    request = ProviderCreateRequest(name="Custom", baseUrl="https://example.com/v1/", protocol="openai_chat_completions", authMode="bearer", apiKey="private-value", expectedRevision=0)
    assert "private-value" not in repr(request)
    assert "apiKey" not in request.model_dump()
    assert request.baseUrl == "https://example.com/v1"


def test_empty_edit_key_preserves_existing_credential():
    payload = dict(name="Custom", baseUrl="https://example.com/v1", protocol="openai_chat_completions",
        authMode="bearer", apiKey="", expectedRevision=1)
    assert ProviderUpdateRequest.model_validate(payload).apiKey is None
    with pytest.raises(ValidationError):
        ProviderCreateRequest.model_validate(payload)


@pytest.mark.parametrize("change", [{"expectedRevision": True}, {"unknown": 1}, {"authMode": "none", "apiKey": "key"}, {"baseUrl": "http://example.com"}, {"apiKey": "bad\r\nheader"}])
def test_strict_mutation_contract(change):
    data = dict(name="Custom", baseUrl="https://example.com", protocol="openai_chat_completions", authMode="bearer", expectedRevision=0)
    data.update(change)
    with pytest.raises(ValidationError):
        ProviderCreateRequest.model_validate(data)
