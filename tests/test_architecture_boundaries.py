"""Import-direction guardrails for package boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PROJECT_ROOT / "src" / "opensprite" / "config"
CHANNELS_ROOT = PROJECT_ROOT / "src" / "opensprite" / "channels"
DOCUMENTS_ROOT = PROJECT_ROOT / "src" / "opensprite" / "documents"
STORAGE_ROOT = PROJECT_ROOT / "src" / "opensprite" / "storage"
TOOLS_ROOT = PROJECT_ROOT / "src" / "opensprite" / "tools"


def _resolved_import(module_path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    relative_module = module_path.relative_to(PROJECT_ROOT / "src").with_suffix("")
    package_parts = list(relative_module.parts[:-1])
    parent_count = node.level - 1
    if parent_count:
        package_parts = package_parts[:-parent_count]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts)


def _find_forbidden_imports(package_root: Path, forbidden_package: str) -> list[str]:
    violations: list[str] = []

    for module_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            imported_modules: list[str] = []
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(_resolved_import(module_path, node))
            else:
                continue

            if any(name == forbidden_package or name.startswith(f"{forbidden_package}.") for name in imported_modules):
                relative_path = module_path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative_path}:{node.lineno}")

    return violations


def test_config_does_not_import_channel_runtime():
    violations = _find_forbidden_imports(CONFIG_ROOT, "opensprite.channels")
    assert violations == [], f"config must not import channel runtime: {violations}"


def test_channels_do_not_import_cli_runtime():
    violations = _find_forbidden_imports(CHANNELS_ROOT, "opensprite.cli")
    assert violations == [], f"channels must use operations services instead of CLI runtime: {violations}"


def test_documents_do_not_import_agent_runtime():
    violations = _find_forbidden_imports(DOCUMENTS_ROOT, "opensprite.agent")
    assert violations == [], f"documents must not import agent runtime: {violations}"


def test_storage_does_not_import_search_runtime():
    violations = _find_forbidden_imports(STORAGE_ROOT, "opensprite.search")
    assert violations == [], f"storage must not import search runtime: {violations}"


def test_tools_do_not_import_agent_runtime():
    violations = _find_forbidden_imports(TOOLS_ROOT, "opensprite.agent")
    assert violations == [], f"tools must not import agent runtime: {violations}"
