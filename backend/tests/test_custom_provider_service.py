import pytest

from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.providers.catalog_store import CatalogError, CustomModel, JsonProviderCatalog
from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction
from opensprite_backend.providers.custom_service import CustomProviderService


def test_custom_provider_configuration_transaction(tmp_path):
    credentials = EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key")
    service = CustomProviderService(ProviderCatalogTransaction(JsonProviderCatalog(tmp_path / "providers.json"), credentials, tmp_path / "transaction.json"))
    fields = dict(name="Custom", base_url="https://example.com/v1", auth_mode="bearer", allow_insecure_local=False)
    with pytest.raises(CatalogError, match="credential_required"):
        service.save(provider_id=None, expected_revision=0, secret=None, **fields)
    record = service.save(provider_id=None, expected_revision=0, secret="private", **fields)
    assert credentials.get(f"provider:{record.id}:bearer") == "private"
    updated = service.save(provider_id=record.id, expected_revision=1, secret=None, **fields)
    assert updated.revision == 2
    assert credentials.get(f"provider:{record.id}:bearer") == "private"
    service.delete(record.id, expected_revision=2)
    assert credentials.get(f"provider:{record.id}:bearer") is None
    assert service.list().providers == ()


def test_model_refresh_preserves_manual_metadata_and_credentials(tmp_path):
    from uuid import uuid4

    credentials = EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key")
    service = CustomProviderService(ProviderCatalogTransaction(JsonProviderCatalog(tmp_path / "providers.json"), credentials, tmp_path / "transaction.json"))
    provider = service.save(provider_id=None, name="Custom", base_url="https://example.com/v1",
        auth_mode="bearer", allow_insecure_local=False, expected_revision=0, secret="private")
    model = CustomModel(key=str(uuid4()), model_id="custom-model", name="My model",
        context_limit=32000, output_limit=4096, tools=True, source="manual")
    provider = service.save_model(provider.id, model, expected_revision=1)
    snapshot = service.execution_endpoint(provider.id)
    refreshed = service.merge_discovered_models(provider.id, ["custom-model", "remote", "remote"], expected_revision=2)
    assert refreshed.models[0] == model
    assert len(refreshed.models) == 2
    remote = refreshed.models[1]
    assert remote.tools is True
    again = service.merge_discovered_models(provider.id, ["remote"], expected_revision=3)
    assert again.models == (model, remote)
    assert credentials.get(f"provider:{provider.id}:bearer") == "private"
    with pytest.raises(CatalogError, match="revision_conflict"):
        service.merge_discovered_models(provider.id, [], expected_revision=3)
    assert service.get(provider.id) == again
    assert len(snapshot.models) == 1
    assert snapshot.models[0].model_id == "custom-model"
    assert snapshot.models[0].context_window_tokens == 32000
    assert snapshot.models[0].supports_tools is True


def test_model_request_defaults_tools_on_but_preserves_explicit_off():
    from opensprite_backend.api.custom_provider_models import ProviderModelRequest

    fields = dict(modelId="test", name="Test", contextLimit=8192,
                  outputLimit=2048, expectedRevision=1)
    assert ProviderModelRequest(**fields).tools is True
    assert ProviderModelRequest(**fields, tools=False).tools is False


def test_endpoint_snapshot_is_not_changed_by_later_configuration(tmp_path):
    from dataclasses import FrozenInstanceError

    credentials = EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key")
    service = CustomProviderService(ProviderCatalogTransaction(JsonProviderCatalog(tmp_path / "providers.json"), credentials, tmp_path / "transaction.json"))
    fields = dict(name="Custom", auth_mode="none", allow_insecure_local=False, secret=None)
    provider = service.save(provider_id=None, base_url="https://example.com/v1", expected_revision=0, **fields)
    snapshot = service.execution_endpoint(provider.id)
    service.save(provider_id=provider.id, base_url="https://other.example/v1", expected_revision=1, **fields)
    assert snapshot.base_url == "https://example.com/v1"
    assert snapshot.revision == 1
    assert service.execution_endpoint(provider.id).revision == 2
    with pytest.raises(FrozenInstanceError):
        snapshot.base_url = "https://changed.example"


def test_model_edit_and_delete_keep_stable_identity_and_credentials(tmp_path):
    from uuid import uuid4

    credentials = EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key")
    service = CustomProviderService(ProviderCatalogTransaction(JsonProviderCatalog(tmp_path / "providers.json"), credentials, tmp_path / "transaction.json"))
    provider = service.save(provider_id=None, name="Custom", base_url="https://example.com/v1",
        auth_mode="bearer", allow_insecure_local=False, expected_revision=0, secret="private")
    model = CustomModel(key=str(uuid4()), model_id="first", name="First",
        context_limit=8192, output_limit=2048, source="manual")
    provider = service.save_model(provider.id, model, expected_revision=1)
    edited = CustomModel.model_validate({**model.model_dump(), "name": "Renamed", "context_limit": 16384})
    provider = service.save_model(provider.id, edited, expected_revision=2)
    assert provider.models == (edited,)
    assert provider.models[0].key == model.key
    with pytest.raises(CatalogError, match="revision_conflict"):
        service.delete_model(provider.id, model.key, expected_revision=2)
    with pytest.raises(CatalogError, match="model_not_found"):
        service.delete_model(provider.id, str(uuid4()), expected_revision=3)
    assert service.get(provider.id) == provider
    removed = service.delete_model(provider.id, model.key, expected_revision=3)
    assert removed.revision == 4
    assert removed.models == ()
    assert credentials.get(f"provider:{provider.id}:bearer") == "private"
    assert service.list().revision == 4
