"""Import guards exercise archive metadata without executing wheel code."""

from io import BytesIO
import stat
import sys
from types import SimpleNamespace
import warnings
from zipfile import ZipFile, ZipInfo

import pytest

from execution_package_test_support import FILE_NAME, INFO, MODULE, GROUP, wheel
from opensprite_backend.execution_plugins.inspection import inspect_wheel
from opensprite_backend.execution_plugins.models import ExecutionPackageError, MAX_WHEEL_BYTES


def test_valid_pure_python_wheel_is_inspected_without_importing_code():
    assert MODULE not in sys.modules
    result = inspect_wheel(wheel(requirements=("opensprite-backend>=0.21.27,<0.22",)), FILE_NAME)
    assert result.distributionName == "opensprite-stage2-fixture"
    assert result.version == "0.1.0"
    assert result.plugins[0].model_dump() == {
        "id": "fixture_loop", "kind": "loop", "apiVersion": 5, "entryPoint": MODULE + ":factory",
    }
    assert MODULE not in sys.modules


@pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", "C:/escape.py", "a\\evil.py", "a/../b.py",
    "a//b.py", "CON.py", "a/trailing./b.py", "opensprite_backend/injected.py", "sitecustomize.py",
    "usercustomize.py", "fixture.pth", "native.so", "native.pyd", "pkg-1.0.data/scripts/start", "os.py"])
def test_unsafe_and_shadowing_files_are_rejected(path):
    with pytest.raises(ExecutionPackageError, match="invalid_package"):
        inspect_wheel(wheel(changes={path: b"blocked"}), FILE_NAME, owners={})


@pytest.mark.parametrize("content", [b"[console_scripts]\nunsafe = stage2_fixture_plugin:factory\n",
    f"[{GROUP}]\nstandard = {MODULE}:factory\n".encode(),
    f"[{GROUP}]\nfixture_loop = missing_module:factory\n".encode(),
    f"[{GROUP}]\nBadID = {MODULE}:factory\n".encode(),
    f"[{GROUP}]\nfixture_loop = {MODULE}:factory\nfixture_loop = {MODULE}:other\n".encode()])
def test_entry_points_are_strict_and_cannot_register_cli_or_builtin(content):
    with pytest.raises(ExecutionPackageError, match="invalid_package"):
        inspect_wheel(wheel(changes={INFO + "/entry_points.txt": content}), FILE_NAME)


def test_unsupported_execution_api_is_rejected_without_importing():
    data = wheel(changes={INFO + "/entry_points.txt": f"[opensprite_backend.agent_loops.v1]\nfixture_loop = {MODULE}:factory\n".encode()})
    with pytest.raises(ExecutionPackageError, match="incompatible_package"):
        inspect_wheel(data, FILE_NAME)
    assert MODULE not in sys.modules


@pytest.mark.parametrize("requirements,python,code", [
    (("missing-for-opensprite-tests>=1",), ">=3.12", "incompatible_package"),
    (("opensprite-backend>=99",), ">=3.12", "incompatible_package"),
    ((), ">=99", "incompatible_package"),
    (("packaging @ https://example.invalid/a.whl",), ">=3.12", "invalid_package"),
    (("packaging[extra]>=1",), ">=3.12", "invalid_package"),
    (("malformed requirement !!",), ">=3.12", "invalid_package"),
])
def test_dependencies_are_validated_without_downloading(requirements, python, code):
    with pytest.raises(ExecutionPackageError, match=code):
        inspect_wheel(wheel(requirements=requirements, requires_python=python), FILE_NAME)


def test_platform_marker_excluded_dependency_does_not_require_download():
    result = inspect_wheel(wheel(requirements=('missing-for-opensprite-tests>=1; sys_platform == "never"',)), FILE_NAME)
    assert len(result.requiresDist) == 1


def test_record_omission_or_content_corruption_is_rejected():
    data = wheel(removed=(MODULE + "/__init__.py",))
    with pytest.raises(ExecutionPackageError, match="invalid_package"):
        inspect_wheel(data, FILE_NAME)
    output = BytesIO()
    with ZipFile(BytesIO(wheel())) as source, ZipFile(output, "w") as target:
        for name in source.namelist():
            target.writestr(name, b"CHANGED" if name.endswith("/__init__.py") else source.read(name))
    with pytest.raises(ExecutionPackageError, match="invalid_package"):
        inspect_wheel(output.getvalue(), FILE_NAME)


def test_duplicate_paths_and_symbolic_links_are_rejected():
    for symbolic in (False, True):
        output = BytesIO()
        with ZipFile(BytesIO(wheel())) as source, ZipFile(output, "w") as target:
            for name in source.namelist():
                target.writestr(name, source.read(name))
            extra = ZipInfo("link.py" if symbolic else MODULE + "/__init__.py")
            if symbolic:
                extra.create_system = 3
                extra.external_attr = (stat.S_IFLNK | 0o777) << 16
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                target.writestr(extra, b"../other")
        with pytest.raises(ExecutionPackageError, match="invalid_package"):
            inspect_wheel(output.getvalue(), FILE_NAME)


def test_declared_wheel_type_and_filename_must_match_metadata():
    for changes, name in (({INFO + "/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-any\n"}, FILE_NAME),
        ({}, "other-0.1.0-py3-none-any.whl"), ({}, FILE_NAME.replace("py3-none-any", "cp312-cp312-linux_x86_64"))):
        with pytest.raises(ExecutionPackageError, match="invalid_package"):
            inspect_wheel(wheel(changes=changes), name)


def test_import_cannot_replace_an_installed_non_plugin_dependency(monkeypatch):
    import opensprite_backend.execution_plugins.inspection as module
    original = module.metadata.distribution
    def installed(name):
        if name == "opensprite-stage2-fixture":
            return SimpleNamespace(entry_points=())
        return original(name)
    monkeypatch.setattr(module.metadata, "distribution", installed)
    with pytest.raises(ExecutionPackageError, match="invalid_package"):
        inspect_wheel(wheel(), FILE_NAME)


def test_size_limit_is_checked_before_zip_parsing():
    with pytest.raises(ExecutionPackageError, match="package_too_large"):
        inspect_wheel(b"x" * (MAX_WHEEL_BYTES + 1), FILE_NAME)
