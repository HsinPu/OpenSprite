"""Dependency-direction guards for Agent, inference, and tool boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "opensprite_backend"


def imported_modules(directory: str) -> list[tuple[str, str]]:
    imports: list[tuple[str, str]] = []
    directory_path = PACKAGE_ROOT / directory
    for source_path in directory_path.rglob("*.py"):
        source_name = source_path.relative_to(directory_path).as_posix()
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append((source_name, node.module))
            elif isinstance(node, ast.Import):
                imports.extend(
                    (source_name, alias.name) for alias in node.names
                )
    return imports


def test_agent_depends_on_interfaces_not_sqlite_or_provider_adapters() -> None:
    forbidden = {
        "opensprite_backend.conversations.sqlite_repository",
        "opensprite_backend.providers.adapters",
        "opensprite_backend.provider_connections",
        "opensprite_backend.app",
        "opensprite_backend.runtime",
        "opensprite_backend.system_prompt",
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


def test_system_prompt_feature_cannot_read_conversations_or_secrets() -> None:
    source_path = PACKAGE_ROOT / "system_prompt.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
    forbidden_prefixes = (
        "opensprite_backend.conversations",
        "opensprite_backend.credentials",
        "opensprite_backend.inference",
        "opensprite_backend.provider",
        "opensprite_backend.tools",
        "opensprite_backend.api",
    )
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert [
        module for module in imports if module.startswith(forbidden_prefixes)
    ] == []


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


def test_provider_connection_policy_has_no_concrete_runtime_composition() -> None:
    source_path = PACKAGE_ROOT / "provider_connections.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
    forbidden_modules = {"httpx", "app_paths", "inference.native_gateway"}
    forbidden_names = {
        "EncryptedJsonCredentialStore",
        "JsonProviderStateRepository",
        "NativeModelGateway",
        "ProviderRuntime",
        "ProviderValidator",
        "create_provider_runtime",
    }
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(
                alias.name
                for alias in node.names
                if alias.name in forbidden_modules
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module in forbidden_modules:
                violations.append(node.module)
            violations.extend(
                alias.name
                for alias in node.names
                if alias.name in forbidden_names
            )
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in forbidden_names:
                violations.append(node.name)

    assert violations == []
