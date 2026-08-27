"""Dependency-direction guards for Agent, inference, and tool boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "opensprite_backend"


def imported_modules(directory: str) -> list[tuple[str, str]]:
    imports: list[tuple[str, str]] = []
    for source_path in (PACKAGE_ROOT / directory).glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append((source_path.name, node.module))
            elif isinstance(node, ast.Import):
                imports.extend(
                    (source_path.name, alias.name) for alias in node.names
                )
    return imports


def test_agent_depends_on_interfaces_not_sqlite_or_provider_adapters() -> None:
    forbidden = {
        "opensprite_backend.conversations.sqlite_repository",
        "opensprite_backend.provider_adapters",
        "opensprite_backend.provider_connections",
        "opensprite_backend.app",
        "opensprite_backend.runtime",
    }

    assert [
        (source, module)
        for source, module in imported_modules("agent")
        if module in forbidden
    ] == []


def test_inference_boundary_has_no_persistence_tool_or_runtime_dependency() -> None:
    forbidden_prefixes = (
        "opensprite_backend.agent",
        "opensprite_backend.app",
        "opensprite_backend.conversations",
        "opensprite_backend.provider_connections",
        "opensprite_backend.runtime",
        "opensprite_backend.tools",
    )

    assert [
        (source, module)
        for source, module in imported_modules("inference")
        if module.startswith(forbidden_prefixes)
    ] == []


def test_tools_do_not_import_agent_inference_persistence_or_providers() -> None:
    forbidden_prefixes = (
        "opensprite_backend.agent",
        "opensprite_backend.conversations",
        "opensprite_backend.inference",
        "opensprite_backend.provider",
        "opensprite_backend.runtime",
    )

    assert [
        (source, module)
        for source, module in imported_modules("tools")
        if module.startswith(forbidden_prefixes)
    ] == []


def test_core_agent_layers_never_depend_back_on_http_api() -> None:
    violations = [
        (directory, source, module)
        for directory in ("agent", "conversations", "inference", "tools")
        for source, module in imported_modules(directory)
        if module.startswith("opensprite_backend.api")
    ]

    assert violations == []


def test_application_layer_has_no_http_or_storage_adapter_dependency() -> None:
    forbidden_prefixes = (
        "fastapi",
        "starlette",
        "opensprite_backend.api",
        "opensprite_backend.app",
        "opensprite_backend.runtime",
        "opensprite_backend.conversations.sqlite_repository",
    )

    assert [
        (source, module)
        for source, module in imported_modules("application")
        if module.startswith(forbidden_prefixes)
    ] == []


def test_app_factory_composes_feature_routers_instead_of_defining_api_routes() -> None:
    app_path = PACKAGE_ROOT / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"), app_path)
    api_routes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            function = decorator.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "app"
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
                and decorator.args[0].value.startswith("/api/")
            ):
                api_routes.append(decorator.args[0].value)

    assert api_routes == []
