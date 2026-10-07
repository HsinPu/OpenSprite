"""Installed plugin discovery, compatibility and failure-boundary checks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
import sys
from types import SimpleNamespace

import pytest

from opensprite_backend.agent.plugin_catalog import (
    ExecutionPluginCatalog,
    ExecutionPluginError,
)
from opensprite_backend.agent.standard_driver import StandardDriverFactory
from opensprite_backend.agent.strategies import StandardExecutionStrategy


LOOPS = "opensprite_backend.agent_loops.v1"
POLICIES = "opensprite_backend.execution_policies.v1"


@dataclass
class InstalledPoint:
    name: str
    group: str
    provider: object
    loads: int = 0
    dist: object = None

    def load(self):
        self.loads += 1
        if isinstance(self.provider, Exception):
            raise self.provider
        return self.provider


def descriptor(catalog, kind, identifier):
    return next(item for item in catalog.descriptors()
                if item.kind == kind and item.id == identifier)


def test_real_distribution_discovery_reads_metadata_without_importing(tmp_path, monkeypatch):
    """Exercise importlib discovery using install-shaped dist-info metadata."""
    distribution = tmp_path / "opensprite_probe-4.2.1.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: opensprite-probe\nVersion: 4.2.1\n"
        "Summary: Installed alternate execution driver.\n", encoding="utf-8")
    (distribution / "entry_points.txt").write_text(
        f"[{LOOPS}]\nprobe = opensprite_installed_probe:provide_factory\n",
        encoding="utf-8")
    import_marker = tmp_path / "plugin-imported"
    (tmp_path / "opensprite_installed_probe.py").write_text(
        "from pathlib import Path\n"
        "from opensprite_backend.agent.standard_driver import StandardDriverFactory\n"
        f"Path({str(import_marker)!r}).write_text('imported', encoding='utf-8')\n"
        "def provide_factory():\n    return StandardDriverFactory()\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("opensprite_installed_probe", None)
    try:
        catalog = ExecutionPluginCatalog()
        item = descriptor(catalog, "loop", "probe")
        assert item.version == "4.2.1"
        assert item.description == "Installed alternate execution driver."
        assert item.api_version == 1 and item.status == "available"
        assert not import_marker.exists()
        assert "opensprite_installed_probe" not in sys.modules

        selection = catalog.resolve("probe", "standard")
        assert import_marker.read_text(encoding="utf-8") == "imported"
        assert selection.loop_version == "4.2.1"
        assert selection.driver_factory.create() is not selection.driver_factory.create()
    finally:
        sys.modules.pop("opensprite_installed_probe", None)


def test_unsupported_api_is_reported_and_never_imported():
    point = InstalledPoint("future", "opensprite_backend.agent_loops.v2",
                           RuntimeError("unsupported code must not execute"))
    catalog = ExecutionPluginCatalog((point,))
    item = descriptor(catalog, "loop", "future")
    assert item.api_version == 2 and item.status == "incompatible"
    with pytest.raises(ExecutionPluginError) as failure:
        catalog.resolve("future", "standard")
    assert failure.value.code == "plugin_unavailable"
    assert point.loads == 0


@pytest.mark.parametrize("kind,group", [("loop", LOOPS), ("policy", POLICIES)])
def test_duplicate_builtin_identifier_is_unavailable_without_import(kind, group):
    point = InstalledPoint("standard", group, RuntimeError("collision"))
    catalog = ExecutionPluginCatalog((point,))
    assert descriptor(catalog, kind, "standard").status == "unavailable"
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("standard", "standard")
    assert point.loads == 0


def test_duplicate_external_identifier_does_not_pick_one_arbitrarily():
    first = InstalledPoint("duplicate", LOOPS, lambda: StandardDriverFactory())
    second = InstalledPoint("duplicate", LOOPS, RuntimeError("second plugin"))
    catalog = ExecutionPluginCatalog((first, second))
    assert descriptor(catalog, "loop", "duplicate").status == "unavailable"
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("duplicate", "standard")
    assert first.loads == second.loads == 0


@pytest.mark.parametrize("provider", [
    RuntimeError("private-plugin-load-detail"),
    lambda: (_ for _ in ()).throw(RuntimeError("private-plugin-load-detail")),
    lambda: object(),
])
def test_selected_load_failure_is_masked_and_marks_plugin_unavailable(provider, caplog):
    point = InstalledPoint("broken", LOOPS, provider)
    catalog = ExecutionPluginCatalog((point,))
    with pytest.raises(ExecutionPluginError) as failure:
        catalog.resolve("broken", "standard")
    assert failure.value.code == "plugin_unavailable"
    assert "private-plugin-load-detail" not in str(failure.value)
    assert "private-plugin-load-detail" not in caplog.text
    assert descriptor(catalog, "loop", "broken").status == "unavailable"
    with pytest.raises(ExecutionPluginError):
        catalog.resolve("broken", "standard")
    assert point.loads == 1


@pytest.mark.parametrize("api_version", [True, 2, "1", None])
def test_selected_factory_must_advertise_exact_api_version(api_version):
    class Factory:
        def create(self):
            return StandardDriverFactory().create()

    factory = Factory()
    factory.api_version = api_version
    point = InstalledPoint("bad_api", LOOPS, lambda: factory)
    catalog = ExecutionPluginCatalog((point,))
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.validate_selection("bad_api", "standard")
    assert descriptor(catalog, "loop", "bad_api").status == "unavailable"


@pytest.mark.parametrize("loop_id,policy_id", [
    ("missing", "standard"), ("standard", "missing"),
    ("../plugin", "standard"), ("standard", ""), (None, "standard"),
])
def test_invalid_selection_does_not_load_external_plugins(loop_id, policy_id):
    point = InstalledPoint("installed", LOOPS, lambda: StandardDriverFactory())
    catalog = ExecutionPluginCatalog((point,))
    with pytest.raises(ExecutionPluginError, match="invalid_request"):
        catalog.resolve(loop_id, policy_id)
    assert point.loads == 0


def test_irrelevant_or_invalid_entrypoints_are_ignored():
    catalog = ExecutionPluginCatalog((
        EntryPoint(name="command", value="never_import:factory", group="console_scripts"),
        EntryPoint(name="../invalid", value="never_import:factory", group=LOOPS),
        EntryPoint(name="zero", value="never_import:factory", group="opensprite_backend.agent_loops.v0"),
    ))
    assert {(item.kind, item.id) for item in catalog.descriptors()} == {
        ("loop", "standard"), ("policy", "standard"), ("policy", "no_recovery"),
    }


def test_selection_preserves_version_and_creates_fresh_policy():
    catalog = ExecutionPluginCatalog(())
    standard = catalog.resolve("standard", "standard")
    no_recovery = catalog.resolve("standard", "no_recovery")
    assert standard.make_strategy() is not standard.make_strategy()
    assert no_recovery.make_strategy() is not no_recovery.make_strategy()
    assert standard.profile() == {
        "loopId": "standard", "loopVersion": "1.0.0",
        "policyId": "standard", "policyVersion": "1.0.0", "apiVersion": 1,
    }
    assert no_recovery.profile()["policyId"] == "no_recovery"


def test_resolved_binding_keeps_factory_and_discovered_version_after_source_changes():
    first_factory = StandardDriverFactory()
    replacement_factory = StandardDriverFactory()
    point = InstalledPoint("pinned", LOOPS, lambda: first_factory,
                           dist=SimpleNamespace(metadata={"Version": "3.2.1", "Summary": "Pinned plugin"}))
    catalog = ExecutionPluginCatalog((point,))
    accepted = catalog.resolve("pinned", "standard")
    point.provider = lambda: replacement_factory
    point.dist.metadata["Version"] = "9.9.9"
    next_binding = catalog.resolve("pinned", "standard")
    assert accepted.driver_factory is first_factory
    assert next_binding.driver_factory is first_factory
    assert accepted.profile()["loopVersion"] == "3.2.1"
    assert next_binding.profile()["loopVersion"] == "3.2.1"
    assert point.loads == 1


def test_cached_factory_with_its_own_load_method_is_not_reloaded():
    class Factory:
        api_version = 1

        def create(self):
            return StandardDriverFactory().create()

        def load(self):
            raise AssertionError("This is a factory asset loader, not an entry-point loader.")

    factory = Factory()
    point = InstalledPoint("asset_loader", LOOPS, lambda: factory)
    catalog = ExecutionPluginCatalog((point,))
    first = catalog.resolve("asset_loader", "standard")
    second = catalog.resolve("asset_loader", "standard")
    assert first.driver_factory is second.driver_factory is factory
    assert first.driver_factory.create() is not second.driver_factory.create()
    assert descriptor(catalog, "loop", "asset_loader").status == "available"
    assert point.loads == 1


@pytest.mark.parametrize("phase", ["import", "provider"])
def test_synchronous_plugin_self_cancellation_is_unavailable_instead_of_request_cancellation(phase):
    def provider():
        raise asyncio.CancelledError("private plugin cancellation detail")

    class Point(InstalledPoint):
        def load(self):
            self.loads += 1
            if phase == "import":
                raise asyncio.CancelledError("private plugin import detail")
            return provider

    point = Point("self_cancelled", LOOPS, provider)
    catalog = ExecutionPluginCatalog((point,))
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("self_cancelled", "standard")
    assert descriptor(catalog, "loop", "self_cancelled").status == "unavailable"
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("self_cancelled", "standard")
    assert point.loads == 1


@pytest.mark.parametrize("version_line", ["Version: \n", "", "Version: " + "1" * 65 + "\n"])
def test_bad_real_distribution_metadata_is_isolated_from_builtin_selection(tmp_path, monkeypatch, version_line):
    from fastapi.testclient import TestClient

    from opensprite_backend.app import create_app
    from opensprite_backend.app_paths import build_app_paths
    from opensprite_backend.execution_settings import ExecutionSettingsService

    distribution = tmp_path / "opensprite_bad_metadata-1.0.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: opensprite-bad-metadata\n" + version_line,
        encoding="utf-8")
    (distribution / "entry_points.txt").write_text(
        f"[{LOOPS}]\nbad_metadata = never_import_bad_metadata:factory\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    catalog = ExecutionPluginCatalog()
    item = descriptor(catalog, "loop", "bad_metadata")
    assert item.status == "unavailable" and item.version == "unknown"
    service = ExecutionSettingsService(build_app_paths(tmp_path / ".opensprite"), catalog)
    with TestClient(create_app(execution_settings=service)) as client:
        read = client.get("/api/settings/execution")
        assert read.status_code == 200
        assert read.json()["selection"] == {"loopId": "standard", "policyId": "standard"}
        assert client.put("/api/settings/execution", json={"loopId": "standard", "policyId": "standard"}).status_code == 200
        assert client.put("/api/settings/execution", json={"loopId": "bad_metadata", "policyId": "standard"}).status_code == 503
    assert asyncio.run(service.get()).selection.loop_id == "standard"
    assert "never_import_bad_metadata" not in sys.modules


def test_policy_creation_failure_does_not_expose_plugin_exception():
    @dataclass
    class Factory:
        api_version: int = 1
        instances: list[object] = field(default_factory=list)

        def create(self):
            raise RuntimeError("private-policy-instantiation-detail")

    point = InstalledPoint("broken_policy", POLICIES, lambda: Factory())
    selection = ExecutionPluginCatalog((point,)).resolve("standard", "broken_policy")
    with pytest.raises(ExecutionPluginError) as failure:
        selection.make_strategy()
    assert str(failure.value) == "plugin_unavailable"


def test_policy_creation_rejects_an_object_without_both_decisions():
    class IncompleteStrategy:
        def allow_context_retry(self, state):
            return True

    class Factory:
        api_version = 1

        def create(self):
            return IncompleteStrategy()

    point = InstalledPoint("incomplete", POLICIES, lambda: Factory())
    selection = ExecutionPluginCatalog((point,)).resolve("standard", "incomplete")
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        selection.make_strategy()


def test_installed_policy_is_selected_without_loading_other_installed_loop():
    class Factory:
        api_version = 1

        def create(self):
            return StandardExecutionStrategy()

    policy = InstalledPoint("installed_policy", POLICIES, lambda: Factory())
    loop = InstalledPoint("installed_loop", LOOPS, RuntimeError("unselected module"))
    selection = ExecutionPluginCatalog((policy, loop)).resolve("standard", "installed_policy")
    assert isinstance(selection.make_strategy(), StandardExecutionStrategy)
    assert policy.loads == 1 and loop.loads == 0
