from uuid import uuid4

import pytest

from opensprite_backend.agent.context.capability_resolver import ModelCapabilityNotFound
from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.model_capability_resolver import ProviderModelCapabilityResolver
from opensprite_backend.providers.catalog_store import CustomModel, JsonProviderCatalog
from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction
from opensprite_backend.providers.custom_service import CustomProviderService


@pytest.mark.anyio
async def test_custom_model_capability_uses_registered_metadata(tmp_path):
    service = CustomProviderService(ProviderCatalogTransaction(
        JsonProviderCatalog(tmp_path / "providers.json"),
        EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key"),
        tmp_path / "transaction.json"))
    provider = service.save(provider_id=None, name="Local", base_url="https://example.com/v1",
        auth_mode="none", allow_insecure_local=False, expected_revision=0, secret=None)
    service.save_model(provider.id, CustomModel(key=str(uuid4()), model_id="local", name="Local model",
        context_limit=16000, output_limit=4000, tools=False, source="manual"), expected_revision=1)
    resolver = ProviderModelCapabilityResolver(None, custom_providers=service)
    capability = await resolver.resolve(provider.id, "local")
    assert capability.context_window_tokens == 16000
    assert capability.max_output_tokens == 4000
    assert capability.supports_tools is False
    with pytest.raises(ModelCapabilityNotFound):
        await resolver.resolve(provider.id, "missing")
    with pytest.raises(ModelCapabilityNotFound):
        await resolver.resolve(str(uuid4()), "local")
