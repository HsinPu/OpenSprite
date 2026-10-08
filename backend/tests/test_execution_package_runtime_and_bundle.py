"""Deployment provenance checks actual file bytes, not only plugin ID/version."""

from io import BytesIO
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

from execution_package_test_support import (FILE_NAME, INFO, MODULE, InstalledDistribution,
                                           absent_distribution, paths, wheel)
from opensprite_backend.execution_plugins.inspection import inspect_wheel
from opensprite_backend.execution_plugins.models import ExecutionPackageError
from opensprite_backend.execution_plugins.runtime_identity import RuntimePackageIdentity, valid_image_ref
from opensprite_backend.execution_plugins.service import ExecutionPackageService

IMAGE = "registry.example/opensprite@sha256:" + "a" * 64


def installation(tmp_path, data):
    inspection = inspect_wheel(data, FILE_NAME)
    site = tmp_path / "site-packages"
    with ZipFile(BytesIO(data)) as archive:
        for name in archive.namelist():
            path = site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    dist = InstalledDistribution(site, inspection)
    manifest = tmp_path / "deployment.json"
    manifest.write_text(json.dumps({"schemaVersion": 1, "baseImage": IMAGE, "packages": [{
        key: inspection.model_dump()[key] for key in ("distributionName", "version", "sha256", "plugins", "files")
    }]}))
    manifest.chmod(0o644)
    return inspection, dist, manifest


def test_manifest_and_exact_wheel_identity_confirm_actual_installed_files(tmp_path):
    data = wheel()
    inspection, dist, manifest = installation(tmp_path, data)
    identity = RuntimePackageIdentity(base_image_ref=IMAGE, runtime_kind="docker", manifest_path=manifest,
                                      distribution_lookup=lambda _: dist)
    runtime, verified = identity.snapshot()
    assert runtime.manifestStatus == "verified"
    assert identity.package_status(inspection, verified) == "confirmed"
    different = inspect_wheel(wheel(changes={MODULE + "/note.txt": b"different wheel, same ID and version"}), FILE_NAME)
    assert different.version == inspection.version
    assert different.plugins == inspection.plugins
    assert identity.package_status(different, verified) == "mismatch"


@pytest.mark.parametrize("change", ["source", "extra-source", "entry-point", "duplicate-package", "duplicate-plugin", "writable-manifest", "duplicate-json-key"])
def test_changed_or_ambiguous_deployment_is_never_confirmed(tmp_path, change):
    inspection, dist, manifest = installation(tmp_path, wheel())
    raw = json.loads(manifest.read_text())
    if change == "source":
        (dist.root / MODULE / "__init__.py").write_text("CHANGED")
    elif change == "extra-source":
        (dist.root / MODULE / "unknown.py").write_text("unrecorded")
    elif change == "entry-point":
        dist.entry_points = []
    elif change == "duplicate-package":
        raw["packages"].append(raw["packages"][0])
        manifest.write_text(json.dumps(raw))
    elif change == "duplicate-plugin":
        raw["packages"][0]["plugins"].append(raw["packages"][0]["plugins"][0])
        manifest.write_text(json.dumps(raw))
    elif change == "writable-manifest":
        if os.name == "nt":
            pytest.skip("POSIX provenance permissions")
        manifest.chmod(0o666)
    else:
        manifest.write_text('{"schemaVersion":1,"schemaVersion":1}')
    identity = RuntimePackageIdentity(runtime_kind="docker", manifest_path=manifest, distribution_lookup=lambda _: dist)
    runtime, verified = identity.snapshot()
    assert runtime.manifestStatus == "invalid"
    assert identity.package_status(inspection, verified) == "unverified"


def test_installed_without_manifest_is_unverified_and_absent_is_not_installed(tmp_path):
    inspection, dist, _ = installation(tmp_path, wheel())
    identity = RuntimePackageIdentity(runtime_kind="local", distribution_lookup=lambda _: dist)
    runtime, manifest = identity.snapshot()
    assert runtime.kind == "local" and runtime.manifestStatus == "missing"
    assert identity.package_status(inspection, manifest) == "unverified"
    absent = RuntimePackageIdentity(distribution_lookup=absent_distribution)
    assert absent.package_status(inspection, None) == "not_installed"


def test_nonregular_manifest_is_invalid_without_opening_the_stream(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO guard")
    manifest = tmp_path / "deployment.json"
    os.mkfifo(manifest, 0o600)
    runtime, value = RuntimePackageIdentity(runtime_kind="docker", manifest_path=manifest).snapshot()
    assert runtime.manifestStatus == "invalid" and value is None


@pytest.mark.parametrize("image", ["opensprite", "opensprite:tag\nRUN echo injected", "opensprite:tag;echo x",
    "$(cat /private)", "registry/image@sha256:bad", "x/../image:tag", "a//b:tag", "UPPER/image:tag"])
def test_image_reference_does_not_accept_shell_or_dockerfile_injection(image):
    with pytest.raises(ExecutionPackageError, match="deployment_unavailable"):
        valid_image_ref(image)


def test_bundle_contains_exact_wheel_and_offline_nonroot_deployment(tmp_path):
    service = ExecutionPackageService(paths(tmp_path), base_image_ref=IMAGE, runtime_kind="docker",
                                     distribution_lookup=absent_distribution)
    data = wheel()
    result = service.import_wheel(FILE_NAME, data)
    downloaded = service.bundle(result.packages[0].id)
    with ZipFile(BytesIO(downloaded)) as archive:
        assert set(archive.namelist()) == {FILE_NAME, "Dockerfile", "compose.override.yaml", "README.md", "validate_deployment.py"}
        assert archive.read(FILE_NAME) == data
        dockerfile = archive.read("Dockerfile").decode()
        assert dockerfile.startswith("FROM " + IMAGE + "\n")
        assert "--no-index --no-deps --force-reinstall" in dockerfile
        assert "-m ensurepip --upgrade" in dockerfile and "-m pip check" in dockerfile
        assert dockerfile.rstrip().endswith("USER opensprite")
        compose = archive.read("compose.override.yaml").decode()
        assert "OPENSPRITE_PLUGIN_BUNDLE_DIR:?" in compose
        assert "volumes:" not in compose and "name:" not in compose
        expected_image = "opensprite:plugin-" + sha256(data).hexdigest()[:16]
        assert "    image: " + expected_image + "\n" in compose
        assert "      OPENSPRITE_DEPLOYMENT_BASE_IMAGE: " + json.dumps(expected_image) + "\n" in compose
        source = archive.read("validate_deployment.py").decode()
        compile(source, "validate_deployment.py", "exec")
        assert "SOURCE_JSON" in source


@pytest.mark.parametrize("same_wheel", [False, True])
def test_next_runtime_deployment_uses_previous_resulting_image_as_base(tmp_path, same_wheel):
    package_paths = paths(tmp_path)
    data_a = wheel()
    image_a = "opensprite:plugin-" + sha256(data_a).hexdigest()[:16]
    first = ExecutionPackageService(package_paths, base_image_ref=IMAGE, runtime_kind="docker",
                                    distribution_lookup=absent_distribution)
    imported_a = first.import_wheel(FILE_NAME, data_a)
    with ZipFile(BytesIO(first.bundle(imported_a.packages[0].id))) as archive:
        assert archive.read("Dockerfile").decode().startswith("FROM " + IMAGE + "\n")
        compose_a = archive.read("compose.override.yaml").decode()
    configured_a = json.loads(next(line.split(": ", 1)[1] for line in compose_a.splitlines()
                                  if line.strip().startswith("OPENSPRITE_DEPLOYMENT_BASE_IMAGE:")))
    assert configured_a == image_a

    # Restart with the setting emitted by A's actual downloaded override.
    second = ExecutionPackageService(package_paths, base_image_ref=configured_a, runtime_kind="docker",
                                     distribution_lookup=absent_distribution)
    assert second.list().runtime.baseImage == image_a
    data_b = data_a if same_wheel else wheel(changes={MODULE + "/note.txt": b"next deployment"})
    image_b = "opensprite:plugin-" + sha256(data_b).hexdigest()[:16]
    imported_b = second.import_wheel(FILE_NAME, data_b)
    package_b = next(item for item in imported_b.packages if item.sha256 == sha256(data_b).hexdigest())
    with ZipFile(BytesIO(second.bundle(package_b.id))) as archive:
        assert archive.read("Dockerfile").decode().startswith("FROM " + image_a + "\n")
        compose_b = archive.read("compose.override.yaml").decode()
        assert "    image: " + image_b + "\n" in compose_b
        configured_b = json.loads(next(line.split(": ", 1)[1] for line in compose_b.splitlines()
                                      if line.strip().startswith("OPENSPRITE_DEPLOYMENT_BASE_IMAGE:")))
        assert configured_b == image_b
        if same_wheel:
            assert "requires the source" in archive.read("README.md").decode()
    restarted = ExecutionPackageService(package_paths, base_image_ref=configured_b, runtime_kind="docker",
                                        distribution_lookup=absent_distribution)
    assert restarted.list().runtime.baseImage == image_b


def test_exported_build_validator_reads_real_dist_info_without_importing_plugin(tmp_path):
    data = wheel()
    _, dist, _ = installation(tmp_path, data)
    service = ExecutionPackageService(paths(tmp_path), base_image_ref=IMAGE, runtime_kind="docker",
                                     distribution_lookup=absent_distribution)
    imported = service.import_wheel(FILE_NAME, data)
    with ZipFile(BytesIO(service.bundle(imported.packages[0].id))) as bundle:
        source = bundle.read("validate_deployment.py").decode()
    source = source.replace('Path("/app/execution-plugin-manifest.json")', f'Path({str(tmp_path / "built-manifest.json")!r})')
    source = source.replace('Path("/opt/opensprite-plugin")', f'Path({str(tmp_path)!r})')
    (tmp_path / FILE_NAME).write_bytes(data)
    script = tmp_path / "validate.py"
    script.write_text(source)
    environment = dict(os.environ, PYTHONPATH=str(dist.root))
    result = subprocess.run([sys.executable, str(script)], env=environment, capture_output=True,
                            text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "built-manifest.json").read_text())
    assert manifest["packages"][0]["sha256"] == imported.packages[0].sha256
    assert manifest["packages"][0]["plugins"] == [{
        "id": "fixture_loop", "kind": "loop", "apiVersion": 3, "entryPoint": MODULE + ":factory",
    }]
    # The fixture module raises if imported; success establishes metadata-only verification.
    assert "IMPORT MUST NOT RUN" not in result.stderr

    (dist.root / MODULE / "__init__.py").write_text("modified after install")
    failed = subprocess.run([sys.executable, str(script)], env=environment, capture_output=True,
                            text=True, timeout=10, check=False)
    assert failed.returncode != 0
    assert failed.stderr.strip() == "Execution plugin deployment verification failed."
    assert "Traceback" not in failed.stderr


@pytest.mark.parametrize("kind,image", [("docker", None), ("local", IMAGE), ("docker", "bad\nFROM attacker")])
def test_missing_or_invalid_deployment_configuration_is_explicit(tmp_path, kind, image):
    service = ExecutionPackageService(paths(tmp_path), base_image_ref=image, runtime_kind=kind,
                                     distribution_lookup=absent_distribution)
    result = service.import_wheel(FILE_NAME, wheel())
    with pytest.raises(ExecutionPackageError, match="deployment_unavailable"):
        service.bundle(result.packages[0].id)
