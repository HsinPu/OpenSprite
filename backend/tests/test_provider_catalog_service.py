from uuid import uuid4

import pytest

from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.providers.custom_service import CustomProviderService
from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction
from opensprite_backend.providers.catalog_store import CatalogError, CustomModel, JsonProviderCatalog


def service_for(tmp_path):
    return CustomProviderService(ProviderCatalogTransaction(
        JsonProviderCatalog(tmp_path / "providers.json"),
        EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key"),
        tmp_path / "transaction.json"))


def test_catalog_lifecycle_and_stale_model_discovery(tmp_path):
    service = service_for(tmp_path)
    provider = service.save(provider_id=None, secret=None, name="Custom", base_url="https://example.com/v1/", auth_mode="none", allow_insecure_local=False, expected_revision=0)
    assert provider.base_url == "https://example.com/v1"
    refreshed = service.merge_discovered_models(provider.id, ["model-a", "model-a"], expected_revision=1)
    assert len(refreshed.models) == 1
    with pytest.raises(CatalogError, match="revision_conflict"):
        service.merge_discovered_models(provider.id, ["stale"], expected_revision=1)
    service.delete(provider.id, expected_revision=2)
    assert service.store.get().providers == ()


def test_discovery_preserves_manual_model_and_metadata(tmp_path):
    service = service_for(tmp_path)
    provider = service.save(provider_id=None, secret=None, name="Custom", base_url="https://example.com", auth_mode="none", allow_insecure_local=False, expected_revision=0)
    manual = CustomModel(key=str(uuid4()), model_id="manual", name="Mine", context_limit=32000, output_limit=4000, tools=True)
    service.save_model(provider.id, manual, expected_revision=1)
    refreshed = service.merge_discovered_models(provider.id, ["manual", "remote"], expected_revision=2)
    assert refreshed.models[0] == manual
    assert len(refreshed.models) == 2
