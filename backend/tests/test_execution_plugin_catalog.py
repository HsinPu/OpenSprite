"""Discovery is metadata-only; one factory creates the complete Run plugin."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib.metadata import EntryPoint
import sys
from types import SimpleNamespace

import pytest
from opensprite_backend.agent.plugin_catalog import ExecutionPluginCatalog, ExecutionPluginError
from opensprite_standard_loop import LoopFactory

LOOPS = "opensprite_backend.agent_loops.v4"

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


def descriptor(catalog, identifier):
    return next(item for item in catalog.descriptors() if item.id == identifier)


def test_real_metadata_discovery_and_validation_never_import_until_resolve(tmp_path, monkeypatch):
    distribution = tmp_path / "opensprite_probe-4.2.1.dist-info"
    distribution.mkdir()
    (distribution / "METADATA").write_text("Metadata-Version: 2.1\nName: opensprite-probe\nVersion: 4.2.1\nSummary: Installed Loop.\n", encoding="utf-8")
    (distribution / "entry_points.txt").write_text(f"[{LOOPS}]\nprobe = opensprite_installed_probe:provide_factory\n", encoding="utf-8")
    marker = tmp_path / "imported"
    (tmp_path / "opensprite_installed_probe.py").write_text(
        "from pathlib import Path\nfrom opensprite_standard_loop import LoopFactory\n"
        f"Path({str(marker)!r}).write_text('imported')\n"
        "def provide_factory():\n    return LoopFactory()\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        catalog = ExecutionPluginCatalog()
        catalog.validate_selection("probe")
        assert descriptor(catalog, "probe").version == "4.2.1"
        assert not marker.exists() and "opensprite_installed_probe" not in sys.modules
        binding = catalog.resolve("probe")
        assert marker.exists()
        assert binding.profile() == {"pluginId": "probe", "pluginVersion": "4.2.1", "apiVersion": 4}
        assert binding.create() is not binding.create()
    finally:
        sys.modules.pop("opensprite_installed_probe", None)


@pytest.mark.parametrize("group", ["opensprite_backend.agent_loops.v1", "opensprite_backend.agent_loops.v2", "opensprite_backend.agent_loops.v3", "opensprite_backend.agent_loops.v5"])
def test_retired_or_future_loops_are_incompatible_without_import(group):
    point = InstalledPoint("other", group, RuntimeError("must not import"))
    catalog = ExecutionPluginCatalog((point,))
    assert descriptor(catalog, "other").status == "incompatible"
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("other")
    assert point.loads == 0


def test_policy_and_cli_groups_are_not_plugin_categories():
    points = tuple(EntryPoint(name="ignored", value="never:factory", group=group) for group in
                   ("opensprite_backend.execution_policies.v2", "opensprite_backend.execution_policies.v3", "console_scripts"))
    assert {item.id for item in ExecutionPluginCatalog(points).descriptors()} == set()


@pytest.mark.parametrize("identifier", ["standard", "no_recovery", "duplicate"])
def test_duplicate_identity_is_not_resolved_arbitrarily(identifier):
    first = InstalledPoint(identifier, LOOPS, lambda: LoopFactory())
    points = (first,) if identifier != "duplicate" else (first, InstalledPoint(identifier, LOOPS, lambda: LoopFactory()))
    catalog = ExecutionPluginCatalog(points)
    assert descriptor(catalog, identifier).status == "unavailable"
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve(identifier)
    assert first.loads == 0


@pytest.mark.parametrize("provider", [RuntimeError("private detail"), lambda: object(), lambda: (_ for _ in ()).throw(RuntimeError("private detail"))])
def test_load_failure_is_sanitized_and_cached(provider, caplog):
    point = InstalledPoint("broken", LOOPS, provider)
    catalog = ExecutionPluginCatalog((point,))
    catalog.validate_selection("broken")
    for _ in range(2):
        with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
            catalog.resolve("broken")
    assert point.loads == 1 and "private detail" not in caplog.text


@pytest.mark.parametrize("api", [True, 2, 3, "4", None])
def test_factory_requires_exact_api_version_at_admission(api):
    factory = SimpleNamespace(api_version=api, create=lambda: LoopFactory().create())
    catalog = ExecutionPluginCatalog((InstalledPoint("bad", LOOPS, lambda: factory),))
    catalog.validate_selection("bad")
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("bad")


@pytest.mark.parametrize("identifier", ["missing", "../plugin", "", None])
def test_bad_selection_never_loads_other_plugins(identifier):
    point = InstalledPoint("installed", LOOPS, lambda: LoopFactory())
    with pytest.raises(ExecutionPluginError, match="invalid_request"):
        ExecutionPluginCatalog((point,)).resolve(identifier)
    assert point.loads == 0


def test_binding_pins_metadata_factory_and_fresh_complete_instances():
    factory = LoopFactory()
    point = InstalledPoint("pinned", LOOPS, lambda: factory, dist=SimpleNamespace(metadata={"Version": "3.2.1", "Summary": "Pinned"}))
    catalog = ExecutionPluginCatalog((point,))
    accepted = catalog.resolve("pinned")
    point.provider = lambda: LoopFactory(True)
    point.dist.metadata["Version"] = "9.9.9"
    assert catalog.resolve("pinned").factory is accepted.factory is factory
    assert accepted.profile()["pluginVersion"] == "3.2.1"
    assert accepted.create() is not accepted.create() and point.loads == 1


@pytest.mark.parametrize("phase", ["load", "provider", "create"])
def test_synchronous_self_cancellation_is_masked(phase):
    def provider():
        if phase == "provider": raise asyncio.CancelledError("private")
        class Factory:
            api_version = 4
            def create(self): raise asyncio.CancelledError("private")
        return Factory()
    class Point(InstalledPoint):
        def load(self):
            if phase == "load": raise asyncio.CancelledError("private")
            return provider
    catalog = ExecutionPluginCatalog((Point("abort", LOOPS, provider),))
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        binding = catalog.resolve("abort")
        binding.create()


@pytest.mark.parametrize("member", ["execute"])
def test_creation_requires_all_methods_on_same_instance(member):
    plugin = LoopFactory().create()
    setattr(plugin, member, None)
    point = InstalledPoint("incomplete", LOOPS, lambda: SimpleNamespace(api_version=4, create=lambda: plugin))
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        ExecutionPluginCatalog((point,)).resolve("incomplete").create()


@pytest.mark.parametrize("version", [None, "", "1" * 65])
def test_invalid_metadata_is_isolated_from_builtins(version):
    point = InstalledPoint("invalid", LOOPS, lambda: None, dist=SimpleNamespace(metadata={"Version": version}))
    catalog = ExecutionPluginCatalog((point,))
    assert descriptor(catalog, "invalid").status == "unavailable"
    assert ExecutionPluginCatalog().resolve("standard").create() is not None
    assert point.loads == 0


@pytest.mark.parametrize("wrapped", [False, True])
def test_async_factory_provider_is_rejected_without_unawaited_coroutine(wrapped):
    async def provider():
        return LoopFactory()
    point = InstalledPoint("async_factory", LOOPS, (lambda: provider()) if wrapped else provider)
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        ExecutionPluginCatalog((point,)).resolve("async_factory")


@pytest.mark.parametrize("wrapped", [False, True])
def test_async_create_is_rejected_without_unawaited_coroutine(wrapped):
    async def create():
        return LoopFactory().create()
    factory = SimpleNamespace(api_version=4, create=(lambda: create()) if wrapped else create)
    catalog = ExecutionPluginCatalog((InstalledPoint("async_create", LOOPS, lambda: factory),))
    with pytest.raises(ExecutionPluginError, match="plugin_unavailable"):
        catalog.resolve("async_create").create()
