from uuid import uuid4

import pytest

from opensprite_backend.credentials.encrypted_json_store import EncryptedJsonCredentialStore
from opensprite_backend.credentials.store import UnsupportedCredentialProviderError


def test_custom_provider_credential_roundtrip_preserves_native(tmp_path):
    path = tmp_path / "auth.json"
    store = EncryptedJsonCredentialStore(path, tmp_path / "credential.key")
    key = f"provider:{uuid4()}:bearer"
    store.set("openai", "original-native-secret")
    store.set(key, "custom-provider-secret")
    assert store.get(key) == "custom-provider-secret"
    assert store.get("openai") == "original-native-secret"
    assert b"custom-provider-secret" not in path.read_bytes()
    store.delete(key)
    assert store.get(key) is None
    assert store.get("openai") == "original-native-secret"


@pytest.mark.parametrize("key", ["provider:bad:bearer", f"provider:{uuid4()}:password", "provider:../../auth:bearer"])
def test_reject_arbitrary_custom_credential_keys(tmp_path, key):
    store = EncryptedJsonCredentialStore(tmp_path / "auth.json", tmp_path / "credential.key")
    with pytest.raises(UnsupportedCredentialProviderError):
        store.set(key, "secret")
