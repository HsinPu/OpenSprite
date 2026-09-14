from uuid import uuid4
import asyncio

import pytest

from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.providers.catalog_store import CustomModel, CustomProvider, JsonProviderCatalog
from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction
from opensprite_backend.providers.custom_service import CustomProviderService
from opensprite_backend.model_capability_resolver import ProviderModelCapabilityResolver


@pytest.fixture
def service(tmp_path):
    return CustomProviderService(ProviderCatalogTransaction(
        JsonProviderCatalog(tmp_path / "providers.json"),
        EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key"),
        tmp_path / "transaction.json"))


FIELDS = dict(name="Test", base_url="https://example.com/v1", auth_mode="none",
              allow_insecure_local=False, secret=None)


def test_new_defaults_and_omitted_update_preserve_choices(service):
    p = service.save(provider_id=None, expected_revision=0, **FIELDS)
    assert p.tools_enabled and p.non_streaming_tools
    p = service.save(provider_id=p.id, expected_revision=p.revision,
                     tools_enabled=False, non_streaming_tools=False, **FIELDS)
    p = service.save(provider_id=p.id, expected_revision=p.revision, **FIELDS)
    assert not p.tools_enabled and not p.non_streaming_tools


def test_legacy_data_keeps_opt_out_and_transport(service):
    p = service.save(provider_id=None, expected_revision=0, **FIELDS)
    old = p.model_dump()
    del old["tools_enabled"]
    del old["non_streaming_tools"]
    restored = CustomProvider.model_validate(old)
    assert restored.tools_enabled and not restored.non_streaming_tools
    model = CustomModel(key=str(uuid4()), model_id="old", name="Old",
                        context_limit=8192, output_limit=2048, tools=False)
    assert not restored.allows_model_tools(model)


@pytest.mark.parametrize("enabled,inherit", [(True, True), (True, False), (False, True), (False, False)])
def test_resolution_and_snapshot_share_policy(service, enabled, inherit):
    p = service.save(provider_id=None, expected_revision=0, tools_enabled=enabled, **FIELDS)
    m = CustomModel(key=str(uuid4()), model_id="model", name="Model",
                    context_limit=8192, output_limit=2048, tools=inherit)
    p = service.save_model(p.id, m, expected_revision=p.revision)
    snapshot = service.execution_endpoint(p.id)
    resolver = ProviderModelCapabilityResolver(None, custom_providers=service)
    assert asyncio.run(resolver.resolve(p.id, m.model_id)).supports_tools == (enabled and inherit)
    assert snapshot.models[0].supports_tools == (enabled and inherit)
    service.save(provider_id=p.id, expected_revision=p.revision, tools_enabled=not enabled, **FIELDS)
    assert snapshot.models[0].supports_tools == (enabled and inherit)


def test_discovery_inherits_and_preserves_disabled_models(service):
    p = service.save(provider_id=None, expected_revision=0, **FIELDS)
    p = service.merge_discovered_models(p.id, ["a", "b"], expected_revision=p.revision)
    assert all(m.tools for m in p.models)
    disabled = p.models[0].model_copy(update={"tools": False, "source": "manual"})
    p = service.save_model(p.id, disabled, expected_revision=p.revision)
    p = service.merge_discovered_models(p.id, ["a", "b", "c"], expected_revision=p.revision)
    assert p.models[0] == disabled
    assert all(m.tools for m in p.models[1:])
