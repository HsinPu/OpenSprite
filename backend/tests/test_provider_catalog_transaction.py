from uuid import uuid4

import pytest

from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.providers.catalog_store import CatalogError, JsonProviderCatalog, ProviderCatalog
from opensprite_backend.providers.catalog_transaction import ProviderCatalogTransaction


def test_transaction_recovers_failed_catalog_write_without_plaintext(tmp_path, monkeypatch):
    store = JsonProviderCatalog(tmp_path / "providers.json")
    credentials = EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "key")
    transaction = ProviderCatalogTransaction(store, credentials, tmp_path / "transaction.json")
    provider_id = str(uuid4())
    original = store.replace
    def fail(*args, **kwargs):
        raise OSError("failure")
    monkeypatch.setattr(store, "replace", fail)
    with pytest.raises(CatalogError):
        transaction.commit(ProviderCatalog(revision=1), provider_id, expected_revision=0, secret="test-secret")
    assert b"test-secret" not in transaction.path.read_bytes()
    assert b"test-secret" not in (tmp_path / "auth.json").read_bytes()
    monkeypatch.setattr(store, "replace", original)
    transaction.recover()
    assert store.get().revision == 1
    assert credentials.get(f"provider:{provider_id}:bearer") == "test-secret"
    assert not transaction.path.exists()
    transaction.recover()
