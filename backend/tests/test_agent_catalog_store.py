"""Strict catalog and no-write-on-read contract."""

import json
from uuid import uuid4

import pytest

from opensprite_backend.app_paths import build_app_paths
from opensprite_backend.custom_agents.models import AgentCatalog, AgentError, AgentRecord
from opensprite_backend.custom_agents.store import AgentCatalogStore


def test_absent_catalog_remains_virtual(tmp_path):
    paths = build_app_paths(tmp_path / "data")
    assert AgentCatalogStore(paths).read() == AgentCatalog()
    assert not paths.home.exists()


def test_roundtrip_records(tmp_path):
    paths = build_app_paths(tmp_path / "data")
    record = AgentRecord(id=str(uuid4()), scope="global", workspaceId=None, fileName="review.toml", name="review", revision=1)
    catalog = AgentCatalog(revision=1, agents=(record,))
    store = AgentCatalogStore(paths)
    store.write(catalog)
    assert store.read() == catalog


@pytest.mark.parametrize("payload", [
    '{"version":1,"version":1}',
    '{"version":1,"unknown":true}',
    '{"version":2}',
    '{"revision":true}',
    '{"enabled":1}',
    '{"agents":{}}',
    'not-json',
    '{}',
])
def test_invalid_catalog_fails_closed(tmp_path, payload):
    paths = build_app_paths(tmp_path)
    paths.config_dir.mkdir()
    paths.agents_settings_file.write_text(payload, encoding="utf-8")
    with pytest.raises(AgentError, match="^store_unavailable$"):
        AgentCatalogStore(paths).read()


def test_duplicate_nested_key_is_rejected(tmp_path):
    paths = build_app_paths(tmp_path)
    paths.config_dir.mkdir()
    paths.agents_settings_file.write_text('{"agents":[{"id":"a","id":"b"}]}')
    with pytest.raises(AgentError):
        AgentCatalogStore(paths).read()


def test_atomic_failure_preserves_previous_catalog(tmp_path, monkeypatch):
    from opensprite_backend import atomic_file

    paths = build_app_paths(tmp_path)
    store = AgentCatalogStore(paths)
    original = AgentCatalog(revision=1)
    store.write(original)

    def fail(*args):
        raise OSError("injected")

    monkeypatch.setattr(atomic_file.os, "replace", fail)
    with pytest.raises(AgentError):
        store.write(AgentCatalog(revision=2, enabled=False))
    assert store.read() == original
    assert not list(paths.config_dir.glob("*.tmp"))


def test_unsafe_filename_is_rejected(tmp_path):
    paths = build_app_paths(tmp_path)
    paths.config_dir.mkdir()
    payload = {"version": 1, "revision": 1, "enabled": True, "agents": [{"id": str(uuid4()), "scope": "global", "workspaceId": None, "fileName": "../escape.toml", "name": "review", "revision": 1}]}
    paths.agents_settings_file.write_text(json.dumps(payload))
    with pytest.raises(AgentError):
        AgentCatalogStore(paths).read()
