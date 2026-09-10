from datetime import UTC, datetime
from uuid import uuid4

import pytest

from opensprite_backend.providers.catalog_store import CatalogError, CustomProvider, JsonProviderCatalog, ProviderCatalog


def provider():
    now = datetime.now(UTC).isoformat()
    return CustomProvider(id=str(uuid4()), name="Local", revision=1, base_url="https://example.com/v1", auth_mode="none", created_at=now, updated_at=now)


def test_catalog_roundtrip_and_revision(tmp_path):
    store = JsonProviderCatalog(tmp_path / "config" / "providers.json")
    assert store.get().revision == 0
    assert not store.path.exists()
    catalog = ProviderCatalog(revision=1, providers=(provider(),))
    store.replace(catalog, expected_revision=0)
    assert store.get() == catalog
    with pytest.raises(CatalogError, match="revision_conflict"):
        store.replace(catalog, expected_revision=0)


def test_atomic_failure_preserves_previous(tmp_path, monkeypatch):
    store = JsonProviderCatalog(tmp_path / "providers.json")
    store.replace(ProviderCatalog(revision=1), expected_revision=0)
    before = store.path.read_bytes()
    def fail(*args):
        raise OSError("private details")
    monkeypatch.setattr("opensprite_backend.providers.catalog_store.atomic_write", fail)
    with pytest.raises(CatalogError, match="provider_store_unavailable"):
        store.replace(ProviderCatalog(revision=2, providers=(provider(),)), expected_revision=1)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("data", ['{"version":1,"revision":0,"revision":1}', '{"version":1,"revision":0,"secret":"no"}', '{"version":1,"revision":true}', '{"version":2}'])
def test_strict_catalog(tmp_path, data):
    path = tmp_path / "providers.json"
    path.write_text(data, encoding="utf-8")
    with pytest.raises(CatalogError):
        JsonProviderCatalog(path).get()
