"""Import-direction guardrails for package boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PROJECT_ROOT / "src" / "opensprite" / "config"


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


def test_config_does_not_import_channel_runtime():
    violations: list[str] = []

    for module_path in sorted(CONFIG_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            imported_modules: list[str] = []
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(_resolved_import(module_path, node))
            else:
                continue

            if any(name == "opensprite.channels" or name.startswith("opensprite.channels.") for name in imported_modules):
                relative_path = module_path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative_path}:{node.lineno}")

    assert violations == [], f"config must not import channel runtime: {violations}"
