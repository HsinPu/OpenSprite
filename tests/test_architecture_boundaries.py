"""Import-direction guardrails for package boundaries."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from sys import stdlib_module_names


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
OPENSPRITE_ROOT = SOURCE_ROOT / "opensprite"
TESTS_ROOT = PROJECT_ROOT / "tests"
AGENT_ROOT = OPENSPRITE_ROOT / "app" / "agent"
AGENT_EXECUTION_SUPPORT_ROOT = AGENT_ROOT / "execution_support"
CONTEXT_ROOT = OPENSPRITE_ROOT / "context"
BUS_ROOT = OPENSPRITE_ROOT / "bus"
APP_ROOT = OPENSPRITE_ROOT / "app"
APP_MESSAGING_ROOT = OPENSPRITE_ROOT / "app" / "messaging"
APP_CLI_ROOT = OPENSPRITE_ROOT / "app" / "cli"
APP_CHANNELS_ROOT = OPENSPRITE_ROOT / "app" / "channels"
APP_DOCUMENT_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "documents"
APP_AUTH_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "auth"
APP_MEDIA_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "media"
APP_MCP_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "mcp"
APP_PROCESS_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "processes"
APP_RUN_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "runs"
APP_SEARCH_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "search"
APP_SCHEDULING_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "scheduling"
APP_SKILLS_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "skills"
APP_SUBAGENT_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "subagents"
APP_VERIFICATION_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "verification"
APP_WEB_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "web"
APP_WORKSPACE_TOOLS_ROOT = OPENSPRITE_ROOT / "app" / "tools" / "workspace"
LEGACY_SUBAGENT_PROMPTS_ROOT = OPENSPRITE_ROOT / "subagent_prompts"
SUBAGENT_PROMPT_RESOURCES_ROOT = OPENSPRITE_ROOT / "resources" / "subagent_prompts"
LEGACY_TEMPLATES_ROOT = OPENSPRITE_ROOT / "templates"
TEMPLATE_RESOURCES_ROOT = OPENSPRITE_ROOT / "resources" / "templates"
MEDIA_ROOT = OPENSPRITE_ROOT / "media"
CORE_ROOT = OPENSPRITE_ROOT / "core"
CORE_CONTRACTS_ROOT = CORE_ROOT / "contracts"
CORE_PORTS_ROOT = CORE_ROOT / "ports"
CORE_RUN_TRACKING_ROOT = CORE_ROOT / "run_tracking"
MODULES_ROOT = OPENSPRITE_ROOT / "modules"
CONVERSATIONS_MODULE_ROOT = MODULES_ROOT / "conversations"
DOCUMENTS_MODULE_ROOT = MODULES_ROOT / "documents"
MEDIA_MODULE_ROOT = MODULES_ROOT / "media"
RUN_MODULES_ROOT = MODULES_ROOT / "runs"
WORKSPACE_MODULE_ROOT = MODULES_ROOT / "workspace"
SKILLS_MODULE_ROOT = MODULES_ROOT / "skills"
SCHEDULING_MODULE_ROOT = MODULES_ROOT / "scheduling"
SEARCH_MODULE_ROOT = MODULES_ROOT / "search"
SESSION_COMMANDS_MODULE_ROOT = MODULES_ROOT / "session_commands"
SUBAGENTS_MODULE_ROOT = MODULES_ROOT / "subagents"
CHANNELS_MODULE_ROOT = MODULES_ROOT / "channels"
TOOLS_MODULE_ROOT = MODULES_ROOT / "tools"
PROCESSES_MODULE_ROOT = MODULES_ROOT / "processes"
INTEGRATIONS_ROOT = OPENSPRITE_ROOT / "integrations"
CONTEXT_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "context"
WORKSPACE_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "workspace"
PERSISTENCE_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "persistence"
MEDIA_PERSISTENCE_MODULE = PERSISTENCE_INTEGRATION_ROOT / "media.py"
SUBAGENTS_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "subagents"
DOCUMENTS_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "documents"
MEDIA_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "media"
SQLITE_PERSISTENCE_ROOT = PERSISTENCE_INTEGRATION_ROOT / "sqlite"
AUTH_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "auth"
MCP_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "mcp"
NETWORK_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "network"
OPERATIONS_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "operations"
PROCESS_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "processes"
VERIFICATION_INTEGRATION_ROOT = INTEGRATIONS_ROOT / "verification"
PROCESS_INTEGRATION_ALLOWED_IMPORTS = (
    "opensprite.core.contracts.bus_events",
    "opensprite.core.contracts.persistence",
    "opensprite.core.contracts.run_events",
    "opensprite.core.logging",
    "opensprite.core.ports.storage",
    "opensprite.integrations.processes",
    "opensprite.modules.processes.runtime_policy",
)
MCP_INTEGRATION_ALLOWED_IMPORTS = (
    "httpx",
    "mcp",
    "opensprite.config.defaults",
    "opensprite.config.json_files",
    "opensprite.config.schema",
    "opensprite.core.contracts.mcp_tools",
    "opensprite.core.contracts.run_events",
    "opensprite.integrations.mcp.naming",
    "opensprite.integrations.mcp.tool_adapter",
    "opensprite.integrations.mcp.transport",
    "opensprite.modules.tools.base",
    "opensprite.modules.tools.registry",
    "opensprite.core.contracts.tool_results",
    "opensprite.core.logging",
)
SEARCH_ROOT = OPENSPRITE_ROOT / "search"
RUNS_ROOT = OPENSPRITE_ROOT / "runs"
STDLIB_MODULES = stdlib_module_names | {"__future__"}
CONFIG_ROOT = PROJECT_ROOT / "src" / "opensprite" / "config"
CHANNELS_ROOT = PROJECT_ROOT / "src" / "opensprite" / "channels"
DOCUMENTS_ROOT = PROJECT_ROOT / "src" / "opensprite" / "documents"
STORAGE_ROOT = PROJECT_ROOT / "src" / "opensprite" / "storage"
TOOLS_ROOT = PROJECT_ROOT / "src" / "opensprite" / "tools"
MEMORY_LEGACY_FACADE_SYMBOLS = frozenset({"consolidate", "consolidate_memory", "memory"})


def test_top_level_source_packages_match_the_declared_architecture():
    package_names = {
        path.name
        for path in OPENSPRITE_ROOT.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    }

    assert package_names == {"app", "config", "core", "integrations", "modules"}
    assert (OPENSPRITE_ROOT / "resources").is_dir()


def _find_spec_or_none(module_name: str):
    try:
        return importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        return None


def _module_name_from_path(module_path: Path) -> str | None:
    try:
        relative_module = module_path.relative_to(SOURCE_ROOT).with_suffix("")
        parts = list(relative_module.parts)
    except ValueError:
        parts = list(module_path.with_suffix("").parts)
        try:
            parts = parts[parts.index("opensprite") :]
        except ValueError:
            return None
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or None


def _resolved_import(module_path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    try:
        relative_module = module_path.relative_to(SOURCE_ROOT).with_suffix("")
    except ValueError:
        relative_module = module_path.relative_to(PROJECT_ROOT).with_suffix("")
    package_parts = list(relative_module.parts[:-1])
    parent_count = node.level - 1
    if parent_count:
        package_parts = package_parts[:-parent_count]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts)


def _imported_modules(module_path: Path, node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    resolved_module = _resolved_import(module_path, node)
    imported_modules = [resolved_module] if resolved_module else []
    imported_modules.extend(
        f"{resolved_module}.{alias.name}" if resolved_module else alias.name
        for alias in node.names
        if alias.name != "*"
    )
    return imported_modules


def _find_forbidden_imports(
    package_root: Path,
    forbidden_package: str,
    *,
    include_submodules: bool = True,
) -> list[str]:
    violations: list[str] = []
    module_paths = (
        [package_root]
        if package_root.is_file()
        else sorted(package_root.rglob("*.py"))
    )

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            imported_modules = _imported_modules(module_path, node)

            if any(
                name == forbidden_package
                or (include_submodules and name.startswith(f"{forbidden_package}."))
                for name in imported_modules
            ):
                try:
                    relative_path = module_path.relative_to(PROJECT_ROOT)
                except ValueError:
                    relative_path = module_path.relative_to(package_root.parent)
                violations.append(f"{relative_path}:{node.lineno}")

    return violations


def _find_forbidden_dynamic_module_or_symbols_access(
    package_root: Path,
    forbidden_module: str,
    symbols: set[str],
    *,
    include_submodules: bool = True,
) -> list[str]:
    """Find string-based module loading, getattr access, or module-level lazy facades."""
    violations: list[str] = []
    architecture_test = Path(__file__).resolve()

    for module_path in sorted(package_root.rglob("*.py")):
        if module_path.resolve() == architecture_test:
            continue
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        try:
            display_path = module_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = module_path.relative_to(package_root)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and (
                    node.value == forbidden_module
                    or (
                        include_submodules
                        and node.value.startswith(f"{forbidden_module}.")
                    )
                )
            ):
                violations.append(f"{display_path}:{node.lineno}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in symbols
            ):
                violations.append(f"{display_path}:{node.lineno}")

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "__getattr__":
                continue
            if any(
                isinstance(child, ast.Constant) and child.value in symbols
                for child in ast.walk(node)
            ):
                violations.append(f"{display_path}:{node.lineno}")

    return sorted(set(violations))


def _find_forbidden_dynamic_module_or_symbol_access(
    package_root: Path,
    forbidden_module: str,
    symbol: str,
) -> list[str]:
    return _find_forbidden_dynamic_module_or_symbols_access(
        package_root,
        forbidden_module,
        {symbol},
    )


def _dotted_attribute_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _find_forbidden_symbols_imports_or_access(
    package_root: Path,
    source_modules: tuple[str, ...],
    symbols: set[str],
) -> list[str]:
    violations: list[str] = []
    source_set = set(source_modules)
    tracked_modules = {
        ".".join(parts[:index])
        for source_module in source_set
        for parts in [source_module.split(".")]
        for index in range(1, len(parts) + 1)
    }

    for module_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        module_aliases: dict[str, set[str]] = {}

        try:
            display_path = module_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = module_path.relative_to(package_root)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        source_module == alias.name
                        or source_module.startswith(f"{alias.name}.")
                        or alias.name.startswith(f"{source_module}.")
                        for source_module in source_set
                    ):
                        bound_name = alias.asname or alias.name.partition(".")[0]
                        imported_module = alias.name if alias.asname else bound_name
                        module_aliases.setdefault(bound_name, set()).add(imported_module)
                continue
            if not isinstance(node, ast.ImportFrom):
                continue

            resolved_module = _resolved_import(module_path, node)
            imported_names = {alias.name for alias in node.names}
            if resolved_module in source_set and (symbols & imported_names or "*" in imported_names):
                violations.append(f"{display_path}:{node.lineno}")

            for alias in node.names:
                imported_module = f"{resolved_module}.{alias.name}" if resolved_module else alias.name
                if any(
                    source_module == imported_module or source_module.startswith(f"{imported_module}.")
                    for source_module in source_set
                ):
                    module_aliases.setdefault(alias.asname or alias.name, set()).add(
                        imported_module
                    )

        alias_assignments: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                reference = _dotted_attribute_name(node.value)
                if reference is None:
                    continue
                alias_assignments.extend(
                    (target.id, reference)
                    for target in node.targets
                    if isinstance(target, ast.Name)
                )
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                reference = _dotted_attribute_name(node.value) if node.value is not None else None
                if reference is not None:
                    alias_assignments.append((node.target.id, reference))

        changed = True
        while changed:
            changed = False
            for target, reference in alias_assignments:
                resolved_modules: set[str] = set()
                for alias, imported_modules in list(module_aliases.items()):
                    if reference != alias and not reference.startswith(f"{alias}."):
                        continue
                    suffix = reference.removeprefix(alias)
                    resolved_modules.update(
                        resolved_module
                        for imported_module in imported_modules
                        if (resolved_module := imported_module + suffix) in tracked_modules
                    )
                target_modules = module_aliases.setdefault(target, set())
                new_modules = resolved_modules - target_modules
                if new_modules:
                    target_modules.update(new_modules)
                    changed = True

        forbidden_attribute_paths = {
            f"{source_module}.{symbol}"
            for source_module in source_set
            for symbol in symbols
        }
        for alias, imported_modules in module_aliases.items():
            for imported_module in imported_modules:
                for source_module in source_set:
                    if source_module == imported_module:
                        forbidden_attribute_paths.update(
                            f"{alias}.{symbol}" for symbol in symbols
                        )
                    elif source_module.startswith(f"{imported_module}."):
                        suffix = source_module.removeprefix(f"{imported_module}.")
                        forbidden_attribute_paths.update(
                            f"{alias}.{suffix}.{symbol}" for symbol in symbols
                        )

        def source_name_matches(name: str) -> bool:
            return any(
                name == source_module
                or name.startswith(f"{source_module}.")
                for source_module in source_set
            )

        def reference_targets_source(reference: str) -> bool:
            if source_name_matches(reference):
                return True
            for alias, imported_modules in module_aliases.items():
                if reference != alias and not reference.startswith(f"{alias}."):
                    continue
                suffix = reference.removeprefix(alias)
                if any(
                    candidate == source_module
                    or candidate.startswith(f"{source_module}.")
                    for imported_module in imported_modules
                    for candidate in (imported_module + suffix,)
                    for source_module in source_set
                ):
                    return True
            return False

        current_module_name = _module_name_from_path(module_path)
        current_module_targets_source = bool(
            current_module_name and source_name_matches(current_module_name)
        )

        def node_targets_source(node: ast.AST) -> bool:
            reference = _dotted_attribute_name(node)
            if reference is not None and reference_targets_source(reference):
                return True
            if isinstance(node, ast.Subscript) and _dotted_attribute_name(node.value) == "sys.modules":
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    return source_name_matches(node.slice.value)
                return (
                    isinstance(node.slice, ast.Name)
                    and node.slice.id == "__name__"
                    and current_module_targets_source
                )
            if isinstance(node, ast.Call) and node.args:
                loader_name = _dotted_attribute_name(node.func)
                if loader_name in {"importlib.import_module", "import_module", "__import__"}:
                    module_name = node.args[0]
                    return (
                        isinstance(module_name, ast.Constant)
                        and isinstance(module_name.value, str)
                        and source_name_matches(module_name.value)
                    )
            return False

        def dynamic_global_symbol(target: ast.AST) -> str | None:
            if not isinstance(target, ast.Subscript):
                return None
            if not (
                isinstance(target.value, ast.Call)
                and isinstance(target.value.func, ast.Name)
                and target.value.func.id == "globals"
            ):
                return None
            if isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str):
                return target.slice.value
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if (
                    _dotted_attribute_name(node) in forbidden_attribute_paths
                    or (
                        node.attr in symbols
                        and node_targets_source(node.value)
                    )
                ):
                    violations.append(f"{display_path}:{node.lineno}")
                    continue
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "setattr"}
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in symbols
            ):
                if node_targets_source(node.args[0]):
                    violations.append(f"{display_path}:{node.lineno}")
                continue
            assignment_targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                assignment_targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                assignment_targets = [node.target]
            if current_module_targets_source and any(
                dynamic_global_symbol(target) in symbols
                for target in assignment_targets
            ):
                violations.append(f"{display_path}:{node.lineno}")

        if current_module_targets_source:
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "__getattr__":
                    continue
                if any(
                    isinstance(child, ast.Constant) and child.value in symbols
                    for child in ast.walk(node)
                ):
                    violations.append(f"{display_path}:{node.lineno}")

    return sorted(set(violations))


def _find_forbidden_symbol_imports_or_access(
    package_root: Path,
    source_modules: tuple[str, ...],
    symbol: str,
) -> list[str]:
    return _find_forbidden_symbols_imports_or_access(
        package_root,
        source_modules,
        {symbol},
    )


def _find_sqlite_search_adapter_dependencies(package_root: Path) -> list[str]:
    violations: list[str] = []

    for module_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(
                    alias.name == "opensprite.integrations.persistence.sqlite.search"
                    or alias.name.startswith("opensprite.integrations.persistence.sqlite.search.")
                    for alias in node.names
                ):
                    violations.append(f"{module_path}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                resolved_import = _resolved_import(module_path, node)
                imported_names = {alias.name for alias in node.names}
                if resolved_import == "opensprite.integrations.persistence.sqlite.search" or (
                    resolved_import == "opensprite.integrations.persistence.sqlite"
                    and ("SQLiteSearchStore" in imported_names or "*" in imported_names)
                ):
                    violations.append(f"{module_path}:{node.lineno}")
            elif isinstance(node, ast.Attribute) and node.attr == "SQLiteSearchStore":
                violations.append(f"{module_path}:{node.lineno}")

    return sorted(set(violations))


def _find_search_query_policy_star_imports(package_root: Path) -> list[str]:
    violations: list[str] = []

    for module_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if _resolved_import(module_path, node) != "opensprite.modules.search.query_policy":
                continue
            if any(alias.name == "*" for alias in node.names):
                violations.append(f"{module_path}:{node.lineno}")

    return violations


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for item in target.elts for name in _assigned_names(item)}
    return set()


def _top_level_bound_names(module_path: Path) -> set[str]:
    """Return names a module exposes through declarations, imports, or assignments."""
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(name for target in node.targets for name in _assigned_names(target))
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                names.update(
                    child.value
                    for child in ast.walk(node.value)
                    if isinstance(child, ast.Constant) and isinstance(child.value, str)
                )
        elif isinstance(node, ast.AnnAssign):
            names.update(_assigned_names(node.target))
    return names


def _class_bound_names(module_path: Path, class_name: str) -> set[str]:
    """Return names declared or assigned directly on one class body."""
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    names: set[str] = set()
    for node in class_node.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(name for target in node.targets for name in _assigned_names(target))
        elif isinstance(node, ast.AnnAssign):
            names.update(_assigned_names(node.target))
    return names


def test_class_bound_names_detects_methods_assignments_and_import_aliases(tmp_path):
    module_path = tmp_path / "sample.py"
    module_path.write_text(
        "class Example:\n"
        "    import json\n"
        "    import pathlib as paths\n"
        "    from collections import Counter as Counts, deque\n"
        "    alias = object()\n"
        "    annotated: str\n"
        "    def method(self):\n"
        "        return None\n",
        encoding="utf-8",
    )

    assert _class_bound_names(module_path, "Example") == {
        "Counts",
        "alias",
        "annotated",
        "deque",
        "json",
        "method",
        "paths",
    }


def _imports_symbols_or_star_from(
    module_path: Path,
    source_module: str,
    symbols: set[str],
) -> bool:
    """Return whether a module imports named symbols or a wildcard from one source."""
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if _resolved_import(module_path, node) != source_module:
            continue
        imported_names = {alias.name for alias in node.names}
        if "*" in imported_names or symbols & imported_names:
            return True
    return False


def _imports_all_symbols_from_without_aliases(
    module_path: Path,
    source_module: str,
    symbols: set[str],
) -> bool:
    """Return whether one import exposes every named symbol without aliases."""
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if _resolved_import(module_path, node) != source_module:
            continue
        imported_names = {alias.name for alias in node.names if alias.asname is None}
        if symbols.issubset(imported_names):
            return True
    return False


def _explicit_all_names(module_path: Path) -> set[str]:
    """Return string names listed in a module's literal ``__all__`` assignment."""
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        if isinstance(value, (list, tuple, set)):
            return {item for item in value if isinstance(item, str)}
    return set()


def _find_imports_outside(
    package_root: Path,
    allowed_packages: tuple[str, ...],
    *,
    allowed_symbol_imports: dict[str, frozenset[str]] | None = None,
) -> list[str]:
    violations: list[str] = []
    allowed_symbol_imports = allowed_symbol_imports or {}
    module_paths = (
        [package_root]
        if package_root.is_file()
        else sorted(package_root.rglob("*.py"))
    )

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.ImportFrom):
                allowed_symbols = allowed_symbol_imports.get(_resolved_import(module_path, node))
                if allowed_symbols is not None and node.names and all(
                    alias.asname is None and alias.name in allowed_symbols
                    for alias in node.names
                ):
                    continue
            imported_modules = _imported_modules(module_path, node)

            for imported_module in imported_modules:
                root_package = imported_module.partition(".")[0]
                if root_package in STDLIB_MODULES:
                    continue
                if any(
                    imported_module == allowed or imported_module.startswith(f"{allowed}.")
                    for allowed in allowed_packages
                ):
                    continue
                try:
                    relative_path = module_path.relative_to(PROJECT_ROOT)
                except ValueError:
                    relative_path = module_path
                violations.append(f"{relative_path}:{node.lineno}:{imported_module}")

    return violations


def test_config_does_not_import_channel_runtime():
    violations = _find_forbidden_imports(CONFIG_ROOT, "opensprite.channels")
    assert violations == [], f"config must not import channel runtime: {violations}"


def test_config_does_not_import_integrations():
    violations = _find_forbidden_imports(CONFIG_ROOT, "opensprite.integrations")
    assert violations == [], f"config must not import integrations: {violations}"


def test_removed_channels_package_and_imports_do_not_return():
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.channels"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.channels"),
    ]

    assert not CHANNELS_ROOT.exists()
    assert _find_spec_or_none("opensprite.channels") is None
    assert violations == []


def test_telegram_adapter_has_one_integration_owner_and_no_legacy_facade():
    symbol = "TelegramAdapter"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/channels/telegram.py")]

    legacy_module = "opensprite.channels.telegram"
    legacy_sources = ("opensprite.channels", legacy_module)
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_dynamic_module_or_symbol_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbol,
        ),
        *_find_forbidden_dynamic_module_or_symbol_access(
            TESTS_ROOT,
            legacy_module,
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_sources,
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            legacy_sources,
            symbol,
        ),
    ]

    assert not (CHANNELS_ROOT / "telegram.py").exists()
    assert (INTEGRATIONS_ROOT / "channels" / "telegram.py").is_file()
    assert not (TESTS_ROOT / "channels" / "test_telegram_media.py").exists()
    assert not (TESTS_ROOT / "channels" / "test_telegram_typing.py").exists()
    assert (TESTS_ROOT / "integrations" / "channels" / "test_telegram_media.py").is_file()
    assert (TESTS_ROOT / "integrations" / "channels" / "test_telegram_typing.py").is_file()
    assert violations == []


def test_dynamic_legacy_module_and_symbol_scanner_covers_runtime_import_shapes(tmp_path):
    cases = {
        "importlib_loader.py": (
            "import importlib\n"
            "module = importlib.import_module('opensprite.channels.telegram')\n"
        ),
        "dunder_loader.py": "module = __import__('opensprite.channels.telegram')\n",
        "dynamic_getattr.py": (
            "import opensprite.channels as channels\n"
            "adapter = getattr(channels, 'TelegramAdapter')\n"
        ),
        "dynamic_facade.py": (
            "def __getattr__(name):\n"
            "    if name == 'TelegramAdapter':\n"
            "        return object()\n"
            "    raise AttributeError(name)\n"
        ),
        "canonical.py": (
            "from opensprite.integrations.channels.telegram import TelegramAdapter\n"
        ),
    }
    for name, source in cases.items():
        (tmp_path / name).write_text(source, encoding="utf-8")

    violations = _find_forbidden_dynamic_module_or_symbol_access(
        tmp_path,
        "opensprite.channels.telegram",
        "TelegramAdapter",
    )

    assert len(violations) == 4
    assert all("canonical.py" not in violation for violation in violations)
    for name in set(cases) - {"canonical.py"}:
        assert any(name in violation for violation in violations)


def test_legacy_symbol_scanner_tracks_dynamic_alias_targets(tmp_path):
    symbol = "reload_mcp_from_config"
    cases = {
        "legacy_getattr.py": (
            "import opensprite.channels as channels\n"
            f"value = getattr(channels, '{symbol}')\n"
        ),
        "legacy_setattr.py": (
            "import opensprite.channels as channels\n"
            f"setattr(channels, '{symbol}', object())\n"
        ),
        "opensprite/channels/legacy_globals.py": f"globals()['{symbol}'] = object()\n",
        "opensprite/channels/legacy_current_module.py": (
            "import sys\n"
            f"setattr(sys.modules[__name__], '{symbol}', object())\n"
        ),
        "opensprite/channels/legacy_current_attribute.py": (
            "import sys\n"
            f"sys.modules[__name__].{symbol} = object()\n"
        ),
        "legacy_sys_modules_constant.py": (
            "import sys\n"
            f"setattr(sys.modules['opensprite.channels'], '{symbol}', object())\n"
        ),
        "legacy_importlib_loader.py": (
            "import importlib\n"
            f"setattr(importlib.import_module('opensprite.channels'), '{symbol}', object())\n"
        ),
        "legacy_importlib_attribute.py": (
            "import importlib\n"
            f"value = importlib.import_module('opensprite.channels').{symbol}\n"
        ),
        "legacy_dunder_loader.py": (
            f"setattr(__import__('opensprite.channels', fromlist=['*']), '{symbol}', object())\n"
        ),
        "opensprite/channels/legacy_lazy_facade.py": (
            "def __getattr__(name):\n"
            f"    if name == '{symbol}':\n"
            "        return object()\n"
            "    raise AttributeError(name)\n"
        ),
        "canonical_getattr.py": (
            "agent = object()\n"
            f"value = getattr(agent, '{symbol}', None)\n"
        ),
        "opensprite/channels/canonical_class_proxy.py": (
            "class Proxy:\n"
            "    def __getattr__(self, name):\n"
            f"        if name == '{symbol}':\n"
            "            return object()\n"
            "        raise AttributeError(name)\n"
        ),
    }
    for name, source in cases.items():
        module_path = tmp_path / name
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(source, encoding="utf-8")

    violations = _find_forbidden_symbols_imports_or_access(
        tmp_path,
        (
            "opensprite.channels",
            "opensprite.channels.web_settings_reload",
        ),
        {symbol},
    )

    allowed = {
        "canonical_getattr.py",
        "opensprite/channels/canonical_class_proxy.py",
    }
    assert len(violations) == 10
    assert all(
        all(Path(name).name not in violation for name in allowed)
        for violation in violations
    )
    for name in set(cases) - allowed:
        assert any(Path(name).name in violation for violation in violations)


def test_web_frontend_runtime_has_one_integration_owner_and_no_legacy_channel_path():
    canonical_root = INTEGRATIONS_ROOT / "web"
    canonical_module = "opensprite.integrations.web.runtime"
    legacy_module = "opensprite.channels.web_frontend_runtime"
    symbol = "run_frontend_command"

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_dynamic_module_or_symbol_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbol,
        ),
        *_find_forbidden_dynamic_module_or_symbol_access(
            TESTS_ROOT,
            legacy_module,
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
    ]

    canonical_initializer = canonical_root / "__init__.py"
    assert symbol not in _top_level_bound_names(canonical_initializer)
    assert symbol not in _explicit_all_names(canonical_initializer)
    assert not _imports_symbols_or_star_from(canonical_initializer, canonical_module, {symbol})
    assert _find_imports_outside(
        canonical_root / "runtime.py",
        ("opensprite.integrations.processes.subprocess_control",),
    ) == []
    assert not (CHANNELS_ROOT / "web_frontend_runtime.py").exists()
    assert (canonical_root / "runtime.py").is_file()
    assert violations == []


def test_web_adapter_has_one_integration_owner_and_no_legacy_facade():
    symbol = "WebAdapter"
    canonical_module = "opensprite.integrations.web.adapter"
    legacy_module = "opensprite.channels.web"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]
    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            {symbol},
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            {symbol},
            include_submodules=False,
        ),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
    ]

    assert owners == [Path("integrations/web/adapter.py")]
    assert not (CHANNELS_ROOT / "web.py").exists()
    assert (INTEGRATIONS_ROOT / "web" / "adapter.py").is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbol not in initializer_names
        assert "__getattr__" not in initializer_names
        assert symbol not in _explicit_all_names(initializer)
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            {symbol},
        )

    assert sorted(set(violations)) == []


def test_web_adapter_only_imports_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "adapter.py",
        (
            "aiohttp",
            "pydantic",
            "opensprite.config",
            "opensprite.core.contracts",
            "opensprite.core.ports.channels",
            "opensprite.integrations.web",
            "opensprite.modules.channels.catalog",
            "opensprite.modules.runs.presentation",
            "opensprite.core.serialization",
            "opensprite.core.logging",
        ),
    )

    assert violations == [], f"WebAdapter must remain integration-owned: {violations}"


def test_web_api_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbol = "WebApiHandlers"
    canonical_module = "opensprite.integrations.web.api"
    legacy_module = "opensprite.channels.web_api"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]
    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            {symbol},
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            {symbol},
            include_submodules=False,
        ),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
    ]

    assert owners == [Path("integrations/web/api.py")]
    assert not (CHANNELS_ROOT / "web_api.py").exists()
    assert (INTEGRATIONS_ROOT / "web" / "api.py").is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbol not in initializer_names
        assert "__getattr__" not in initializer_names
        assert symbol not in _explicit_all_names(initializer)
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            {symbol},
        )

    assert sorted(set(violations)) == []


def test_web_api_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "api.py",
        (
            "aiohttp",
            "opensprite.core.contracts.channel_identity",
            "opensprite.modules.session_commands.catalog",
        ),
        allowed_symbol_imports={
            "opensprite.integrations.web": frozenset(
                {
                    "run_handlers",
                    "session_handlers",
                }
            ),
        },
    )

    assert violations == [], f"Web API handlers must remain integration-owned: {violations}"


def test_web_run_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "handle_run_events",
        "handle_runs",
        "handle_run_trace",
        "handle_run_summary",
        "handle_run_cancel",
        "handle_run_file_change_revert",
    }
    expected_path = Path("integrations/web/run_handlers.py")
    canonical_module = "opensprite.integrations.web.run_handlers"
    legacy_module = "opensprite.channels.web_api_runs"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        for symbol in symbols & _top_level_bound_names(module_path):
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "web_api_runs.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )

    assert sorted(set(violations)) == []


def test_web_run_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "run_handlers.py",
        (
            "aiohttp",
            "opensprite.core.contracts.channel_identity",
            "opensprite.modules.runs.presentation",
            "opensprite.modules.runs.session_entries",
        ),
    )

    assert violations == [], f"Web run handlers must remain integration-owned: {violations}"


def test_web_session_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "handle_sessions",
        "handle_sessions_delete",
        "handle_session_status",
        "serialize_session_summary",
    }
    expected_path = Path("integrations/web/session_handlers.py")
    canonical_module = "opensprite.integrations.web.session_handlers"
    legacy_module = "opensprite.channels.web_api_sessions"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        for symbol in symbols & _top_level_bound_names(module_path):
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "web_api_sessions.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )

    assert sorted(set(violations)) == []


def test_web_session_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "session_handlers.py",
        (
            "aiohttp",
            "opensprite.core.contracts.channel_identity",
            "opensprite.core.contracts.messages",
            "opensprite.modules.runs.presentation",
            "opensprite.modules.runs.session_entries",
        ),
    )

    assert violations == [], f"Web session handlers must remain integration-owned: {violations}"


def test_web_routes_have_one_integration_owner_and_no_legacy_facade():
    symbol = "register_web_routes"
    canonical_module = "opensprite.integrations.web.routes"
    legacy_module = "opensprite.channels.web_routes"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]
    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            {symbol},
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            {symbol},
            include_submodules=False,
        ),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbol,
        ),
    ]

    assert owners == [Path("integrations/web/routes.py")]
    assert not (CHANNELS_ROOT / "web_routes.py").exists()
    assert (INTEGRATIONS_ROOT / "web" / "routes.py").is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbol not in initializer_names
        assert "__getattr__" not in initializer_names
        assert symbol not in _explicit_all_names(initializer)
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            {symbol},
        )

    assert sorted(set(violations)) == []


def test_web_routes_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "routes.py",
        ("opensprite.core.logging",),
        allowed_symbol_imports={
            "opensprite.integrations.web": frozenset({"cron_handlers"}),
            "opensprite.integrations.web.settings": frozenset(
                {"app_handlers", "core_handlers", "provider_handlers", "tool_handlers"}
            ),
        },
    )

    assert violations == [], f"Web routes must remain integration-owned: {violations}"


def test_web_cron_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "cron_default_timezone",
        "require_cron_manager",
        "get_cron_service",
        "require_session_id",
        "split_session_for_cron",
        "build_cron_schedule_from_payload",
        "serialize_cron_job",
        "handle_cron_jobs",
        "handle_cron_job_create",
        "handle_cron_job_update",
        "handle_cron_job_delete",
        "handle_cron_job_action",
    }
    unique_symbols = symbols - {"get_cron_service"}
    expected_path = Path("integrations/web/cron_handlers.py")
    canonical_module = "opensprite.integrations.web.cron_handlers"
    legacy_module = "opensprite.channels.web_cron_api"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in unique_symbols}
    cron_service_owners: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in unique_symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))
        if "get_cron_service" in bound_names:
            cron_service_owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in unique_symbols}
    assert cron_service_owners == [
        Path("app/cli/commands_cron.py"),
        expected_path,
    ]
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_cron_api.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert not (TESTS_ROOT / "channels" / "test_web_cron_api.py").exists()
    assert (TESTS_ROOT / "integrations" / "web" / "test_cron_handlers.py").is_file()

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )

    assert sorted(set(violations)) == []


def test_web_cron_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "cron_handlers.py",
        (
            "aiohttp",
            "opensprite.config",
            "opensprite.modules.scheduling.manager",
            "opensprite.modules.scheduling.presentation",
            "opensprite.modules.scheduling.types",
        ),
    )

    assert violations == [], f"Web cron handlers must remain integration-owned: {violations}"


def test_web_settings_coercion_has_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "coerce_text_list",
        "apply_optional_secret_field",
        "coerce_log_level",
        "coerce_positive_int",
        "coerce_float_range",
        "coerce_bool",
        "_coerce_choice",
        "coerce_browser_backend",
        "coerce_web_search_provider",
        "coerce_web_search_freshness",
        "normalize_searxng_engine_options",
        "normalize_searxng_category_options",
        "searxng_options_payload",
        "searxng_config_url",
    }
    expected_path = Path("integrations/web/settings/coercion.py")
    canonical_module = "opensprite.integrations.web.settings.coercion"
    legacy_module = "opensprite.channels.web_settings_coercion"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_coercion.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )

    assert sorted(set(violations)) == []


def test_web_settings_coercion_only_imports_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "coercion.py",
        (
            "aiohttp",
            "opensprite.config",
            "opensprite.core.contracts.web_search",
            "opensprite.integrations.search.searxng_http",
        ),
    )

    assert violations == [], f"Web settings coercion must remain integration-owned: {violations}"


def test_searxng_http_helpers_have_one_integration_owner_and_no_legacy_module():
    symbols = {
        "SEARXNG_MAX_RESPONSE_BYTES",
        "normalize_searxng_proxy_url",
        "read_limited_searxng_json",
        "searxng_endpoint_url",
    }
    expected_path = Path("integrations/search/searxng_http.py")
    canonical_module = "opensprite.integrations.search.searxng_http"
    legacy_module = "opensprite.utils.searxng_url"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "utils" / "searxng_url.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(INTEGRATIONS_ROOT / "search" / "__init__.py"))
    assert _find_forbidden_imports(
        INTEGRATIONS_ROOT / "search" / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert sorted(set(violations)) == []


def test_searxng_provider_has_one_integration_owner_and_no_legacy_tool_module():
    symbols = {
        "clean_text_values",
        "search_searxng",
        "searxng_scope_params",
    }
    expected_path = Path("integrations/search/searxng.py")
    canonical_module = "opensprite.integrations.search.searxng"
    legacy_module = "opensprite.tools.web_search_searxng"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "tools" / "web_search_searxng.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(INTEGRATIONS_ROOT / "search" / "__init__.py"))
    assert _find_forbidden_imports(
        INTEGRATIONS_ROOT / "search" / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(
        OPENSPRITE_ROOT / expected_path,
        (
            "httpx",
            "opensprite.integrations.search.searxng_http",
            "opensprite.modules.search.presentation",
            "opensprite.modules.search.web_policy",
        ),
    ) == []
    assert sorted(set(violations)) == []


def test_duckduckgo_provider_has_one_integration_owner_and_no_legacy_tool_module():
    symbol = "search_duckduckgo"
    expected_path = Path("integrations/search/duckduckgo.py")
    canonical_module = "opensprite.integrations.search.duckduckgo"
    legacy_module = "opensprite.tools.web_search_duckduckgo"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == [expected_path]
    assert not (OPENSPRITE_ROOT / "tools" / "web_search_duckduckgo.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbol not in _top_level_bound_names(INTEGRATIONS_ROOT / "search" / "__init__.py")
    assert _find_forbidden_imports(
        INTEGRATIONS_ROOT / "search" / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(
        OPENSPRITE_ROOT / expected_path,
        (
            "ddgs",
            "loguru",
            "opensprite.modules.search.presentation",
            "opensprite.modules.search.web_policy",
        ),
    ) == []
    assert sorted(set(violations)) == []


def test_web_search_policy_has_one_module_owner_and_no_legacy_tool_module():
    symbols = {
        "DUCKDUCKGO_FRESHNESS",
        "FRESHNESS_VALUES",
        "PROVIDER_FRESHNESS_PARAM_FIELDS",
        "freshness_params",
        "normalize_freshness",
        "web_search_request",
    }
    expected_path = Path("modules/search/web_policy.py")
    canonical_module = "opensprite.modules.search.web_policy"
    legacy_module = "opensprite.tools.web_search_freshness"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "tools" / "web_search_freshness.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(MODULES_ROOT / "search" / "__init__.py"))
    assert _find_forbidden_imports(
        MODULES_ROOT / "search" / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(
        OPENSPRITE_ROOT / expected_path,
        ("opensprite.core.contracts.web_search",),
    ) == []
    assert sorted(set(violations)) == []


def test_web_search_tool_parameters_have_one_tool_module_owner_and_no_legacy_tool_module():
    symbols = {"web_search_parameters"}
    expected_path = Path("modules/tools/web_search_parameters.py")
    canonical_module = "opensprite.modules.tools.web_search_parameters"
    legacy_module = "opensprite.tools.web_search_parameters"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "tools" / "web_search_parameters.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(TOOLS_MODULE_ROOT / "__init__.py"))
    assert _find_forbidden_imports(
        TOOLS_MODULE_ROOT / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(
        OPENSPRITE_ROOT / expected_path,
        (
            "opensprite.modules.search.web_policy",
            "opensprite.modules.tools.validation",
        ),
    ) == []
    assert sorted(set(violations)) == []


def test_web_access_policy_has_one_tool_module_owner_and_no_legacy_tool_module():
    symbols = {
        "WEB_BLOCKING_RULE",
        "WebBlockingRule",
        "looks_blocked_or_challenge",
    }
    expected_path = Path("modules/tools/web_access_policy.py")
    canonical_module = "opensprite.modules.tools.web_access_policy"
    legacy_module = "opensprite.tools.web_blocking"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "tools" / "web_blocking.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(TOOLS_MODULE_ROOT / "__init__.py"))
    assert _find_forbidden_imports(
        TOOLS_MODULE_ROOT / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(OPENSPRITE_ROOT / expected_path, ()) == []
    assert sorted(set(violations)) == []


def test_web_search_provider_contract_values_have_one_core_owner():
    symbols = {
        "DEFAULT_WEB_SEARCH_PROVIDER",
        "WEB_SEARCH_FRESHNESS_OPTIONS",
        "WEB_SEARCH_PROVIDERS",
    }
    expected_path = Path("core/contracts/web_search.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols.isdisjoint(_top_level_bound_names(CONFIG_ROOT / "defaults.py"))
    assert symbols.isdisjoint(_top_level_bound_names(CORE_CONTRACTS_ROOT / "__init__.py"))


def test_web_search_provider_routing_has_one_module_owner_and_no_legacy_tool_module():
    symbols = {
        "WebSearchProvider",
        "normalize_web_search_provider",
        "web_search_provider",
    }
    expected_path = Path("modules/search/provider_routing.py")
    canonical_module = "opensprite.modules.search.provider_routing"
    legacy_module = "opensprite.tools.web_search_dispatch"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "tools" / "web_search_dispatch.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(MODULES_ROOT / "search" / "__init__.py"))
    assert _find_forbidden_imports(
        MODULES_ROOT / "search" / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(
        OPENSPRITE_ROOT / expected_path,
        ("opensprite.core.contracts.web_search",),
    ) == []
    assert sorted(set(violations)) == []


def test_web_search_presentation_has_one_module_owner_and_no_legacy_tool_module():
    symbols = {
        "format_error",
        "format_results",
        "normalize_text",
        "strip_tags",
    }
    expected_path = Path("modules/search/presentation.py")
    canonical_module = "opensprite.modules.search.presentation"
    legacy_module = "opensprite.tools.web_search_payloads"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (OPENSPRITE_ROOT / "tools" / "web_search_payloads.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert symbols.isdisjoint(_top_level_bound_names(MODULES_ROOT / "search" / "__init__.py"))
    assert _find_forbidden_imports(
        MODULES_ROOT / "search" / "__init__.py",
        canonical_module,
        include_submodules=False,
    ) == []
    assert _find_imports_outside(
        OPENSPRITE_ROOT / expected_path,
        ("opensprite.modules.search",),
    ) == []
    assert sorted(set(violations)) == []


def test_web_settings_payloads_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "network_payload",
        "browser_payload",
        "web_search_payload",
        "log_payload",
    }
    expected_path = Path("integrations/web/settings/payloads.py")
    canonical_module = "opensprite.integrations.web.settings.payloads"
    legacy_module = "opensprite.channels.web_settings_payloads"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_payloads.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )

    assert sorted(set(violations)) == []


def test_web_settings_payloads_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "payloads.py",
        (
            "opensprite.config",
            "opensprite.core.contracts.web_search",
            "opensprite.integrations.web.settings",
        ),
    )

    assert violations == [], f"Web settings payloads must remain integration-owned: {violations}"


def test_web_settings_reload_has_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "_reload_agent_runtime_from_config",
        "reload_agent_llm_from_config",
        "reload_channels_from_config",
        "reload_schedule_from_config",
        "reload_media_from_config",
        "reload_web_search_from_config",
        "reload_browser_from_config",
        "reload_mcp_from_config",
    }
    unique_symbols = symbols - {"reload_agent_llm_from_config"}
    expected_path = Path("integrations/web/settings/reload.py")
    canonical_module = "opensprite.integrations.web.settings.reload"
    legacy_module = "opensprite.channels.web_settings_reload"
    owners: dict[str, list[Path]] = {symbol: [] for symbol in unique_symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in unique_symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            ("opensprite.channels", legacy_module),
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in unique_symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_reload.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert not (TESTS_ROOT / "channels" / "test_web_settings_reload.py").exists()
    assert (TESTS_ROOT / "integrations" / "web" / "settings" / "test_reload.py").is_file()

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )

    assert sorted(set(violations)) == []


def test_web_settings_reload_only_imports_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "reload.py",
        (
            "opensprite.config",
            "opensprite.integrations.web.settings",
        ),
    )

    assert violations == [], f"Web settings reload must remain integration-owned: {violations}"


def test_web_settings_support_has_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "get_provider_settings",
        "get_channel_settings",
        "get_schedule_settings",
        "get_mcp_settings",
        "get_media_settings",
        "mcp_runtime_payload",
        "with_mcp_runtime",
        "read_json_body",
        "_raise_settings_error",
        "raise_provider_settings_error",
        "provider_settings_errors",
        "raise_channel_settings_error",
        "raise_credential_store_error",
        "raise_schedule_settings_error",
        "raise_mcp_settings_error",
    }
    legacy_leaf = "web_settings_support"
    legacy_export_symbols = symbols | {legacy_leaf}
    expected_path = Path("integrations/web/settings/support.py")
    canonical_module = "opensprite.integrations.web.settings.support"
    legacy_module = "opensprite.channels.web_settings_support"
    legacy_sources = ("opensprite.channels", legacy_module)
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_support.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert not (TESTS_ROOT / "channels" / "test_channel_settings.py").exists()
    assert (TESTS_ROOT / "integrations" / "web" / "settings" / "test_support.py").is_file()

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert legacy_export_symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert legacy_export_symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )
        assert not _imports_symbols_or_star_from(
            initializer,
            "opensprite.integrations.web.settings",
            {"support"},
        )
        assert _find_forbidden_imports(
            initializer,
            canonical_module,
            include_submodules=False,
        ) == []

    assert sorted(set(violations)) == []


def test_web_settings_support_avoids_app_channel_adapter_registry():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "support.py",
        (
            "aiohttp",
            "opensprite.app.settings.media",
            "opensprite.app.settings.providers",
            "opensprite.modules.llm.provider_errors",
            "opensprite.integrations.auth.credentials",
            "opensprite.integrations.mcp.settings",
            "opensprite.modules.channels",
            "opensprite.modules.scheduling.settings",
        ),
    )

    assert violations == [], f"Web settings support must remain integration-owned: {violations}"


def test_web_settings_support_leaf_facade_guard_detects_canonical_alias(tmp_path):
    initializer = tmp_path / "__init__.py"
    initializer.write_text(
        "from opensprite.integrations.web.settings import support as web_settings_support\n"
        "import opensprite.integrations.web.settings.support as support\n",
        encoding="utf-8",
    )

    assert "web_settings_support" in _top_level_bound_names(initializer)
    assert _imports_symbols_or_star_from(
        initializer,
        "opensprite.integrations.web.settings",
        {"support"},
    )
    assert _find_forbidden_imports(
        initializer,
        "opensprite.integrations.web.settings.support",
        include_submodules=False,
    )


def test_web_provider_settings_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "_provider_id_from_request",
        "handle_settings_providers",
        "handle_settings_provider_connect",
        "handle_settings_provider_disconnect",
        "handle_settings_credentials",
        "handle_settings_credential_create",
        "handle_settings_credential_delete",
        "handle_settings_credential_default",
        "handle_settings_provider_credential",
        "handle_settings_models",
    }
    legacy_leaf = "web_settings_handlers_provider"
    legacy_export_symbols = symbols | {legacy_leaf}
    expected_path = Path("integrations/web/settings/provider_handlers.py")
    canonical_module = "opensprite.integrations.web.settings.provider_handlers"
    legacy_module = "opensprite.channels.web_settings_handlers_provider"
    legacy_sources = ("opensprite.channels", legacy_module)
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_handlers_provider.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert legacy_export_symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert legacy_export_symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )
        assert not _imports_symbols_or_star_from(
            initializer,
            "opensprite.integrations.web.settings",
            {"provider_handlers"},
        )
        assert _find_forbidden_imports(
            initializer,
            canonical_module,
            include_submodules=False,
        ) == []

    assert sorted(set(violations)) == []


def test_web_provider_settings_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "provider_handlers.py",
        (
            "aiohttp",
            "opensprite.integrations.auth.credentials",
            "opensprite.integrations.web.settings",
            "opensprite.core.logging",
        ),
    )

    assert violations == [], f"Web provider settings handlers must remain integration-owned: {violations}"


def test_web_core_settings_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "handle_settings_codex_auth_status",
        "handle_settings_codex_auth_login",
        "handle_settings_codex_auth_poll",
        "handle_settings_codex_auth_logout",
        "handle_settings_copilot_auth_status",
        "handle_settings_copilot_auth_login",
        "handle_settings_copilot_auth_poll",
        "handle_settings_copilot_auth_logout",
        "handle_settings_channels",
        "handle_settings_channel_create",
        "handle_settings_channel_update",
        "handle_settings_channel_connect",
        "handle_settings_channel_disconnect",
    }
    legacy_leaf = "web_settings_handlers_core"
    legacy_export_symbols = symbols | {legacy_leaf}
    expected_path = Path("integrations/web/settings/core_handlers.py")
    canonical_module = "opensprite.integrations.web.settings.core_handlers"
    legacy_module = "opensprite.channels.web_settings_handlers_core"
    legacy_sources = ("opensprite.channels", legacy_module)
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_handlers_core.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert legacy_export_symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert legacy_export_symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )
        assert not _imports_symbols_or_star_from(
            initializer,
            "opensprite.integrations.web.settings",
            {"core_handlers"},
        )
        assert _find_forbidden_imports(
            initializer,
            canonical_module,
            include_submodules=False,
        ) == []

    assert sorted(set(violations)) == []


def test_web_core_settings_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "core_handlers.py",
        (
            "aiohttp",
            "opensprite.integrations.auth.codex",
            "opensprite.integrations.auth.copilot",
            "opensprite.integrations.web.settings",
            "opensprite.modules.channels",
            "opensprite.core.logging",
        ),
    )

    assert violations == [], f"Web core settings handlers must remain integration-owned: {violations}"


def test_web_app_settings_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "handle_settings_media",
        "handle_settings_media_update",
        "handle_settings_model_select",
        "build_update_status_payload",
        "handle_settings_update_status",
        "restart_gateway_after_response",
        "handle_settings_update_apply",
        "handle_settings_schedule",
        "handle_settings_schedule_update",
        "handle_settings_network",
        "handle_settings_network_update",
    }
    legacy_leaf = "web_settings_handlers_app"
    legacy_export_symbols = symbols | {legacy_leaf}
    expected_path = Path("integrations/web/settings/app_handlers.py")
    canonical_module = "opensprite.integrations.web.settings.app_handlers"
    legacy_module = "opensprite.channels.web_settings_handlers_app"
    legacy_sources = ("opensprite.channels", legacy_module)
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_handlers_app.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert legacy_export_symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert legacy_export_symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )
        assert not _imports_symbols_or_star_from(
            initializer,
            "opensprite.integrations.web.settings",
            {"app_handlers"},
        )
        assert _find_forbidden_imports(
            initializer,
            canonical_module,
            include_submodules=False,
        ) == []

    assert sorted(set(violations)) == []


def test_web_app_settings_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "app_handlers.py",
        (
            "aiohttp",
            "opensprite.config",
            "opensprite.integrations.network.environment",
            "opensprite.integrations.operations",
            "opensprite.integrations.web.settings",
            "opensprite.core.logging",
        ),
    )

    assert violations == [], f"Web app settings handlers must remain integration-owned: {violations}"


def test_web_tool_settings_handlers_have_one_integration_owner_and_no_legacy_facade():
    symbols = {
        "SEARXNG_OPTIONS_USER_AGENT",
        "_browser_command_prefix",
        "_browser_runtime_status",
        "_run_browser_doctor_command",
        "_run_browser_install_command",
        "_with_browser_diagnostic",
        "_browser_payload",
        "handle_settings_web_search",
        "handle_settings_web_search_searxng_options",
        "handle_settings_web_search_update",
        "handle_settings_browser",
        "handle_settings_browser_update",
        "handle_settings_browser_test",
        "handle_settings_browser_doctor",
        "handle_settings_browser_install",
        "handle_settings_log",
        "handle_settings_log_update",
        "handle_settings_mcp",
        "handle_settings_mcp_create",
        "handle_settings_mcp_update",
        "handle_settings_mcp_delete",
        "handle_settings_mcp_reload",
    }
    legacy_leaf = "web_settings_handlers_tools"
    legacy_export_symbols = symbols | {legacy_leaf}
    expected_path = Path("integrations/web/settings/tool_handlers.py")
    canonical_module = "opensprite.integrations.web.settings.tool_handlers"
    legacy_module = "opensprite.channels.web_settings_handlers_tools"
    legacy_sources = ("opensprite.channels", legacy_module)
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(
            OPENSPRITE_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_imports(
            TESTS_ROOT,
            legacy_module,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            set(),
            include_submodules=False,
        ),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            legacy_sources,
            legacy_export_symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert symbols <= _top_level_bound_names(OPENSPRITE_ROOT / expected_path)
    assert not (CHANNELS_ROOT / "web_settings_handlers_tools.py").exists()
    assert (OPENSPRITE_ROOT / expected_path).is_file()
    assert _find_spec_or_none(legacy_module) is None

    for initializer in (
        INTEGRATIONS_ROOT / "web" / "__init__.py",
        INTEGRATIONS_ROOT / "web" / "settings" / "__init__.py",
    ):
        initializer_names = _top_level_bound_names(initializer)
        assert legacy_export_symbols.isdisjoint(initializer_names)
        assert "__getattr__" not in initializer_names
        assert legacy_export_symbols.isdisjoint(_explicit_all_names(initializer))
        assert not _imports_symbols_or_star_from(
            initializer,
            canonical_module,
            symbols,
        )
        assert not _imports_symbols_or_star_from(
            initializer,
            "opensprite.integrations.web.settings",
            {"tool_handlers"},
        )
        assert _find_forbidden_imports(
            initializer,
            canonical_module,
            include_submodules=False,
        ) == []

    assert sorted(set(violations)) == []


def test_web_tool_settings_handlers_only_import_integration_dependencies():
    violations = _find_imports_outside(
        INTEGRATIONS_ROOT / "web" / "settings" / "tool_handlers.py",
        (
            "aiohttp",
            "httpx",
            "opensprite.config",
            "opensprite.integrations.browser",
            "opensprite.integrations.web",
            "opensprite.integrations.web.settings",
            "opensprite.integrations.search.searxng_http",
            "opensprite.core.logging",
            "opensprite.integrations.observability.logging",
            "opensprite.modules.tools.browser_navigation",
        ),
    )

    assert violations == [], f"Web tool settings handlers must remain integration-owned: {violations}"


def test_browser_runtime_has_one_integration_owner_and_no_legacy_tool_modules():
    expected_owners = {
        "BrowserRuntimeError": Path("integrations/browser/provider_base.py"),
        "CloudBrowserSession": Path("integrations/browser/provider_base.py"),
        "CloudBrowserProvider": Path("integrations/browser/provider_base.py"),
        "BrowserbaseCloudProvider": Path("integrations/browser/providers.py"),
        "BrowserUseCloudProvider": Path("integrations/browser/providers.py"),
        "FirecrawlCloudProvider": Path("integrations/browser/providers.py"),
        "cloud_provider_from_config": Path("integrations/browser/factory.py"),
        "browser_cloud_status": Path("integrations/browser/factory.py"),
        "BROWSER_CLOUD_PROVIDER_TYPES": Path("integrations/browser/factory.py"),
        "AgentBrowserRuntime": Path("integrations/browser/runtime.py"),
        "SUPPORTED_BROWSER_BACKENDS": Path("integrations/browser/runtime.py"),
        "resolve_cdp_url": Path("integrations/browser/runtime.py"),
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in expected_owners}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        bound_names = _top_level_bound_names(module_path)
        for symbol in expected_owners.keys() & bound_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_modules = (
        "opensprite.tools.browser_provider_base",
        "opensprite.tools.browser_providers",
        "opensprite.tools.browser_provider_factory",
        "opensprite.tools.browser_runtime",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            source = module_path.read_text(encoding="utf-8-sig")
            if any(legacy_module in source for legacy_module in legacy_modules):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == {
        symbol: [expected_path]
        for symbol, expected_path in expected_owners.items()
    }
    assert all(
        not (TOOLS_ROOT / f"{legacy_module.rsplit('.', 1)[-1]}.py").exists()
        for legacy_module in legacy_modules
    )
    assert all(_find_spec_or_none(legacy_module) is None for legacy_module in legacy_modules)
    assert _top_level_bound_names(INTEGRATIONS_ROOT / "browser" / "__init__.py") == set()
    assert _find_imports_outside(
        INTEGRATIONS_ROOT / "browser",
        (
            "httpx",
            "opensprite.config.defaults",
            "opensprite.core.url",
            "opensprite.integrations.browser",
            "opensprite.integrations.processes.subprocess_control",
        ),
    ) == []
    assert sorted(set(violations)) == []


def test_browser_tests_follow_production_ownership():
    tool_test = TESTS_ROOT / "app" / "tools" / "web" / "test_browser.py"
    legacy_tool_test = TESTS_ROOT / "tools" / "test_browser.py"
    integration_test_root = TESTS_ROOT / "integrations" / "browser"
    integration_tests = {
        "factory": integration_test_root / "test_browser_factory.py",
        "runtime": integration_test_root / "test_browser_runtime.py",
        "providers": integration_test_root / "test_browser_providers.py",
    }

    assert tool_test.is_file()
    assert not legacy_tool_test.exists()
    assert all(module_path.is_file() for module_path in integration_tests.values())
    assert _find_forbidden_imports(tool_test, "opensprite.integrations.browser") == []
    assert _find_forbidden_imports(integration_test_root, "opensprite.tools") == []
    assert _find_forbidden_imports(integration_test_root, "opensprite.app") == []

    tool_test_names = {
        name for name in _top_level_bound_names(tool_test) if name.startswith("test_")
    }
    integration_test_names = {
        owner: {
            name
            for name in _top_level_bound_names(module_path)
            if name.startswith("test_")
        }
        for owner, module_path in integration_tests.items()
    }

    assert tool_test_names == {
        "test_browser_click_and_type_normalize_refs",
        "test_browser_console_reads_or_evaluates_page_context",
        "test_browser_navigate_allows_private_urls_when_configured",
        "test_browser_navigate_blocks_private_urls_by_default",
        "test_browser_navigate_blocks_secret_bearing_urls",
        "test_browser_navigate_uses_current_session_and_open_command",
        "test_browser_snapshot_uses_compact_mode_by_default",
    }
    assert integration_test_names == {
        "factory": {
            "test_browser_cloud_status_reports_registered_cloud_backends",
            "test_cloud_provider_factory_uses_selected_browser_backend",
        },
        "runtime": {
            "test_agent_browser_runtime_builds_json_command",
            "test_agent_browser_runtime_passes_launch_args_for_managed_session",
            "test_agent_browser_runtime_reports_missing_runtime",
            "test_agent_browser_runtime_uses_cdp_backend_without_session",
            "test_agent_browser_runtime_uses_cloud_provider_cdp_session",
        },
        "providers": {
            "test_browser_use_provider_accepts_full_browsers_base_url",
            "test_browser_use_provider_creates_cdp_session",
            "test_browserbase_provider_avoids_duplicate_v1_path",
            "test_browserbase_provider_creates_and_closes_cdp_session",
            "test_firecrawl_provider_avoids_duplicate_v2_path",
            "test_firecrawl_provider_creates_cdp_session",
        },
    }


def test_config_does_not_import_llm_runtime():
    violations = _find_forbidden_imports(CONFIG_ROOT, "opensprite.llms")
    assert violations == [], f"config must not import LLM runtime: {violations}"


def test_reasoning_policy_symbols_have_one_canonical_owner():
    symbols = {
        "VALID_REASONING_EFFORTS",
        "REASONING_EFFORT_OPTIONS",
        "DEFAULT_REASONING_EFFORT",
        "normalize_reasoning_effort",
        "is_valid_reasoning_effort",
        "reasoning_config_from_effort",
        "reasoning_config_or_default",
        "reasoning_effort_from_config",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/llm/reasoning.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_reasoning_policy_only_imports_standard_library():
    module_path = MODULES_ROOT / "llm" / "reasoning.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_reasoning_policy_has_one_module_owner_and_no_legacy_modules():
    symbols = {
        "VALID_REASONING_EFFORTS",
        "REASONING_EFFORT_OPTIONS",
        "DEFAULT_REASONING_EFFORT",
        "normalize_reasoning_effort",
        "is_valid_reasoning_effort",
        "reasoning_config_from_effort",
        "reasoning_config_or_default",
        "reasoning_effort_from_config",
    }
    canonical_module = "opensprite.modules.llm.reasoning"
    legacy_modules = (
        "opensprite.config.reasoning",
        "opensprite.llms.reasoning",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    initializer = MODULES_ROOT / "llm" / "__init__.py"
    assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)

    assert (MODULES_ROOT / "llm" / "reasoning.py").is_file()
    assert not (CONFIG_ROOT / "reasoning.py").exists()
    assert not (OPENSPRITE_ROOT / "llms" / "reasoning.py").exists()
    assert (TESTS_ROOT / "modules" / "llm" / "test_reasoning.py").is_file()
    assert not (TESTS_ROOT / "config" / "test_reasoning.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert all(_find_spec_or_none(module) is None for module in legacy_modules)
    assert violations == []


def test_bundled_subagent_prompt_assets_live_under_resources():
    legacy_assets = sorted(LEGACY_SUBAGENT_PROMPTS_ROOT.glob("*.md"))
    resource_assets = sorted(SUBAGENT_PROMPT_RESOURCES_ROOT.glob("*.md"))

    assert legacy_assets == []
    assert len(resource_assets) == 22
    assert {path.name for path in resource_assets} >= {
        "code-reviewer.md",
        "implementer.md",
        "researcher.md",
        "writer.md",
    }


def test_bundled_template_assets_live_under_resources():
    resource_assets = sorted(TEMPLATE_RESOURCES_ROOT.glob("*.md"))

    assert not LEGACY_TEMPLATES_ROOT.exists()
    assert _find_spec_or_none("opensprite.templates") is None
    assert {path.name for path in resource_assets} == {
        "AGENTS.md",
        "IDENTITY.md",
        "SOUL.md",
        "TOOLS.md",
        "USER.md",
    }
    assert (TEMPLATE_RESOURCES_ROOT / "memory" / "MEMORY.md").is_file()


def test_agent_visible_text_and_log_redaction_only_import_standard_library():
    violations: list[str] = []
    for module_path in (
        AGENT_EXECUTION_SUPPORT_ROOT / "assistant_visible_text.py",
        AGENT_EXECUTION_SUPPORT_ROOT / "log_redaction.py",
    ):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for imported_module in _imported_modules(module_path, node):
                if imported_module.partition(".")[0] not in STDLIB_MODULES:
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}:{imported_module}")

    assert violations == []


def test_agent_visible_text_and_log_redaction_symbols_have_canonical_owners():
    expected_owners = {
        "_find_code_regions": Path("app/agent/execution_support/assistant_visible_text.py"),
        "_is_inside_code": Path("app/agent/execution_support/assistant_visible_text.py"),
        "_strip_tag_blocks": Path("app/agent/execution_support/assistant_visible_text.py"),
        "strip_assistant_internal_scaffolding": Path("app/agent/execution_support/assistant_visible_text.py"),
        "sanitize_assistant_visible_text": Path("app/agent/execution_support/assistant_visible_text.py"),
        "_mask_secret": Path("app/agent/execution_support/log_redaction.py"),
        "_redact_query_string": Path("app/agent/execution_support/log_redaction.py"),
        "redact_log_preview": Path("app/agent/execution_support/log_redaction.py"),
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in expected_owners}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in owners:
                owners[node.name].append(relative_path)

    assert owners == {symbol: [path] for symbol, path in expected_owners.items()}


def test_legacy_agent_text_and_log_redaction_utils_do_not_return():
    legacy_modules = (
        "opensprite.utils.assistant_visible_text",
        "opensprite.utils.log_redaction",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            source = module_path.read_text(encoding="utf-8-sig")
            if any(legacy_module in source for legacy_module in legacy_modules):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    legacy_symbols = {
        "sanitize_assistant_visible_text",
        "strip_assistant_internal_scaffolding",
        "redact_log_preview",
    }
    assert not (OPENSPRITE_ROOT / "utils" / "assistant_visible_text.py").exists()
    assert not (OPENSPRITE_ROOT / "utils" / "log_redaction.py").exists()
    assert all(_find_spec_or_none(module_name) is None for module_name in legacy_modules)
    assert not (OPENSPRITE_ROOT / "utils").exists()
    assert not (TESTS_ROOT / "utils" / "test_assistant_visible_text.py").exists()
    assert (TESTS_ROOT / "agent" / "execution_support" / "test_assistant_visible_text.py").is_file()
    assert violations == []


def test_subagent_module_policies_only_import_core_contracts_and_ports():
    violations = _find_imports_outside(
        SUBAGENTS_MODULE_ROOT,
        (
            "opensprite.core.contracts.llm",
            "opensprite.core.contracts.tool_names",
            "opensprite.core.ports.llm",
        ),
    )

    assert violations == []


def test_subagent_profile_policy_symbols_have_one_canonical_owner():
    symbols = {
        "TOOL_PROFILE_METADATA_FIELD",
        "TOOL_PROFILE_NAMES",
        "SubagentToolProfile",
        "TOOL_PROFILES_BY_NAME",
        "PARALLEL_SAFE_PROFILE_NAMES",
        "SUBAGENT_TOOL_PROFILES",
        "normalize_metadata_value",
        "allowed_tool_profile_names",
        "validate_tool_profile_name",
        "profile_for_subagent",
        "supports_parallel_delegation",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/subagents/profiles.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_legacy_subagent_profile_module_does_not_return():
    legacy_module = "opensprite.subagent_prompts.profiles"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert not (LEGACY_SUBAGENT_PROMPTS_ROOT / "profiles.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "modules" / "subagents" / "test_profiles.py").is_file()
    assert violations == []


def test_subagent_prompt_repository_only_imports_workspace_paths():
    violations = _find_imports_outside(
        SUBAGENTS_INTEGRATION_ROOT,
        ("opensprite.integrations.workspace.paths",),
    )

    assert violations == []


def test_workspace_resource_provisioning_symbols_have_canonical_owners():
    expected_owners = {
        "BOOTSTRAP_FILES": Path("integrations/workspace/bootstrap.py"),
        "load_bootstrap_files": Path("integrations/workspace/bootstrap.py"),
        "sync_subagent_prompts_from_package": Path("integrations/subagents/prompts.py"),
        "sync_templates": Path("integrations/workspace/bootstrap.py"),
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in expected_owners}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(
            module_path.read_text(encoding="utf-8-sig"),
            filename=str(module_path),
        )
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for symbol in expected_owners.keys() & declared_names:
                owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {
        symbol: [expected_path]
        for symbol, expected_path in expected_owners.items()
    }
    assert "BOOTSTRAP_FILES" not in (
        CONTEXT_INTEGRATION_ROOT / "file_builder.py"
    ).read_text(encoding="utf-8-sig")

    legacy_module = "opensprite.context.paths"
    violations: list[str] = []
    for symbol in expected_owners:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                (legacy_module,),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                (legacy_module,),
                symbol,
            )
        )
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert expected_owners.keys().isdisjoint(_top_level_bound_names(initializer))

    assert (
        TESTS_ROOT / "integrations" / "workspace" / "test_workspace_bootstrap.py"
    ).is_file()
    assert violations == []


def test_workspace_bootstrap_adapter_dependencies_stay_explicit():
    violations = _find_imports_outside(
        WORKSPACE_INTEGRATION_ROOT,
        (
            "opensprite.core.session_identity",
            "opensprite.integrations.subagents.prompts",
            "opensprite.integrations.workspace.paths",
        ),
    )

    assert violations == []


def test_workspace_paths_have_one_canonical_owner_and_no_legacy_context_package():
    legacy_package = "opensprite.context"
    legacy_module = "opensprite.context.paths"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert not CONTEXT_ROOT.exists()
    assert _find_spec_or_none(legacy_package) is None
    assert _find_spec_or_none(legacy_module) is None
    assert (WORKSPACE_INTEGRATION_ROOT / "paths.py").is_file()
    assert (TESTS_ROOT / "integrations" / "workspace" / "test_workspace_paths.py").is_file()
    assert not (TESTS_ROOT / "context").exists()
    assert _top_level_bound_names(WORKSPACE_INTEGRATION_ROOT / "__init__.py") == set()
    assert violations == []


def test_tool_workspace_path_helpers_have_one_integration_owner_and_adapters_use_them():
    canonical_module = "opensprite.integrations.workspace.paths"
    canonical_path = WORKSPACE_INTEGRATION_ROOT / "paths.py"
    integration_test_path = TESTS_ROOT / "integrations" / "workspace" / "test_workspace_paths.py"
    symbols = {"resolve_workspace_root", "resolve_workspace_path", "build_workspace_resolver"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    adapter_symbols = {
        APP_WORKSPACE_TOOLS_ROOT / "filesystem.py": {"resolve_workspace_path", "build_workspace_resolver"},
        APP_WORKSPACE_TOOLS_ROOT / "code_navigation.py": {"resolve_workspace_path", "build_workspace_resolver"},
        APP_VERIFICATION_TOOLS_ROOT / "verify.py": {"resolve_workspace_path", "build_workspace_resolver"},
        APP_PROCESS_TOOLS_ROOT / "exec.py": {"build_workspace_resolver"},
    }

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        definitions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for symbol in symbols & definitions:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert _find_spec_or_none(canonical_module) is not None
    assert owners == {symbol: [Path("integrations/workspace/paths.py")] for symbol in symbols}
    for adapter_path, required_symbols in adapter_symbols.items():
        assert _imports_all_symbols_from_without_aliases(adapter_path, canonical_module, required_symbols)
    assert integration_test_path.is_file()
    assert _find_forbidden_imports(integration_test_path, "opensprite.app") == []
    assert _find_imports_outside(canonical_path, ("opensprite.core.session_identity",)) == []


def test_subagent_prompt_repository_symbols_have_one_canonical_owner():
    symbols = {
        "_split_frontmatter",
        "_parse_frontmatter",
        "_session_subagent_dir",
        "_get_prompt_path",
        "load_metadata",
        "load_prompt",
        "load_all_metadata",
        "get_all_subagents",
        "get_prompt_types",
        "has_prompt",
        "read_prompt_document",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("integrations/subagents/prompts.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_legacy_subagent_prompts_package_does_not_return():
    legacy_package = "opensprite.subagent_prompts"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_package in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not LEGACY_SUBAGENT_PROMPTS_ROOT.exists()
    assert _find_spec_or_none(legacy_package) is None
    assert not (TESTS_ROOT / "subagent_prompts").exists()
    assert (TESTS_ROOT / "integrations" / "subagents" / "test_executable_coding_prompts.py").is_file()
    assert (TESTS_ROOT / "integrations" / "subagents" / "test_session_workspace_merge.py").is_file()
    assert _top_level_bound_names(SUBAGENTS_INTEGRATION_ROOT / "__init__.py") == set()
    assert violations == []


def test_legacy_cli_package_does_not_return():
    legacy_package = "opensprite.cli"
    root_entrypoint = OPENSPRITE_ROOT / "__main__.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert not (OPENSPRITE_ROOT / "cli").exists()
    assert _find_spec_or_none(legacy_package) is None
    assert not (TESTS_ROOT / "cli").exists()
    assert APP_CLI_ROOT.is_dir()
    assert (TESTS_ROOT / "app" / "cli").is_dir()
    assert _imports_all_symbols_from_without_aliases(
        root_entrypoint,
        "opensprite.app.cli.commands",
        {"app"},
    )
    assert violations == []


def _find_app_cli_dependency_violations(package_root: Path) -> list[str]:
    return _find_imports_outside(
        package_root,
        (
            "aiohttp",
            "typer",
            "opensprite.app.bootstrap",
            "opensprite.app.cli",
            "opensprite.app.llm",
            "opensprite.app.lifecycle",
            "opensprite.app.runtime",
            "opensprite.config",
            "opensprite.integrations.workspace.paths",
            "opensprite.core.contracts",
            "opensprite.core.ports.channels",
            "opensprite.integrations.auth",
            "opensprite.integrations.network.environment",
            "opensprite.integrations.operations",
            "opensprite.integrations.persistence.sqlite.search",
            "opensprite.modules.runs.presentation",
            "opensprite.modules.scheduling",
            "opensprite.core.serialization",
            "opensprite.core.logging",
            "opensprite.integrations.observability.logging",
        ),
        allowed_symbol_imports={"opensprite": frozenset({"__version__"})},
    )


def test_app_cli_only_imports_application_dependencies():
    violations = _find_app_cli_dependency_violations(APP_CLI_ROOT)

    assert violations == []


def test_cli_chat_adapter_has_one_canonical_owner_and_no_channel_alias():
    symbols = {"CliAdapter", "CliChatResult"}
    expected_path = Path("app/cli/chat_adapter.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.channels.cli"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "cli.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "app" / "cli" / "test_chat_cli.py").is_file()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert violations == []


def test_app_cli_dependency_guard_rejects_root_package_imports(tmp_path):
    package_root = tmp_path / "app_cli"
    package_root.mkdir()
    (package_root / "plain_root.py").write_text("import opensprite\n", encoding="utf-8")
    (package_root / "wildcard.py").write_text("from opensprite import *\n", encoding="utf-8")

    assert len(_find_app_cli_dependency_violations(package_root)) == 2


def test_legacy_documents_package_does_not_return():
    legacy_package = "opensprite.documents"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert not DOCUMENTS_ROOT.exists()
    assert _find_spec_or_none(legacy_package) is None
    assert violations == []


def test_removed_operation_audit_record_does_not_return():
    symbol = "OperationAuditRecord"
    legacy_module = "opensprite.ops.audit"
    source_modules = ("opensprite.ops", legacy_module)
    owners = [
        module_path.relative_to(PROJECT_ROOT).as_posix()
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_symbol_imports_or_access(OPENSPRITE_ROOT, source_modules, symbol),
        *_find_forbidden_symbol_imports_or_access(TESTS_ROOT, source_modules, symbol),
    ]

    assert not (OPENSPRITE_ROOT / "ops" / "audit.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert owners == []
    assert violations == []


def test_legacy_ops_package_does_not_return():
    legacy_package = "opensprite.ops"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert not (OPENSPRITE_ROOT / "ops").exists()
    assert _find_spec_or_none(legacy_package) is None
    assert not (TESTS_ROOT / "cli" / "test_service_background.py").exists()
    assert not (TESTS_ROOT / "cli" / "test_service_linux.py").exists()
    assert not (TESTS_ROOT / "cli" / "test_update_cli.py").exists()
    assert (TESTS_ROOT / "integrations" / "operations" / "test_service_background.py").is_file()
    assert (TESTS_ROOT / "integrations" / "operations" / "test_service_linux.py").is_file()
    assert (TESTS_ROOT / "integrations" / "operations" / "test_update_cli.py").is_file()
    assert violations == []


def test_operations_integrations_only_import_host_support():
    violations = _find_imports_outside(
        OPERATIONS_INTEGRATION_ROOT,
        (
            "opensprite.integrations.operations",
            "opensprite.integrations.processes.subprocess_control",
        ),
    )

    assert violations == []


def test_subprocess_control_has_one_process_integration_owner_and_no_legacy_utils_module():
    canonical_module = "opensprite.integrations.processes.subprocess_control"
    legacy_module = "opensprite.utils.processes"
    canonical_path = INTEGRATIONS_ROOT / "processes" / "subprocess_control.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert canonical_path.is_file()
    assert not (OPENSPRITE_ROOT / "utils" / "processes.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_logging_facade_and_setup_have_clear_owners_and_no_legacy_utils_package():
    facade_module = "opensprite.core.logging"
    setup_module = "opensprite.integrations.observability.logging"
    legacy_module = "opensprite.utils.log"
    facade_path = CORE_ROOT / "logging.py"
    setup_path = INTEGRATIONS_ROOT / "observability" / "logging.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert facade_path.is_file()
    assert setup_path.is_file()
    assert not (OPENSPRITE_ROOT / "utils").exists()
    assert not (TESTS_ROOT / "utils").exists()
    assert _find_spec_or_none(facade_module) is not None
    assert _find_spec_or_none(setup_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert "setup_log" not in _top_level_bound_names(facade_path)
    assert "setup_log" in _top_level_bound_names(setup_path)
    assert _find_imports_outside(facade_path, ("loguru",)) == []
    assert _find_imports_outside(setup_path, ("opensprite.core.logging",)) == []
    assert violations == []


def test_legacy_bus_package_does_not_return():
    legacy_package = "opensprite.bus"
    public_symbols = {"MessageQueue", "Conversation"}
    initializer = OPENSPRITE_ROOT / "__init__.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert not BUS_ROOT.exists()
    assert _find_spec_or_none(legacy_package) is None
    assert not (TESTS_ROOT / "bus").exists()
    assert (TESTS_ROOT / "app" / "messaging" / "test_dispatcher.py").is_file()
    assert public_symbols.issubset(_top_level_bound_names(initializer))
    assert public_symbols.issubset(_explicit_all_names(initializer))
    assert _imports_all_symbols_from_without_aliases(
        initializer,
        "opensprite.app.messaging.dispatcher",
        public_symbols,
    )
    assert violations == []


def test_app_messaging_facade_guard_rejects_aliases(tmp_path):
    module_path = tmp_path / "__init__.py"
    module_path.write_text(
        "from opensprite.app.messaging.dispatcher import (\n"
        "    ResponseHandler as MessageQueue,\n"
        "    ErrorHandler as Conversation,\n"
        ")\n",
        encoding="utf-8",
    )

    assert not _imports_all_symbols_from_without_aliases(
        module_path,
        "opensprite.app.messaging.dispatcher",
        {"MessageQueue", "Conversation"},
    )


def test_app_messaging_only_imports_application_dependencies():
    violations = _find_imports_outside(
        APP_MESSAGING_ROOT,
        (
            "opensprite.app.messaging",
            "opensprite.config",
            "opensprite.core.contracts",
            "opensprite.modules.documents.scope",
            "opensprite.modules.scheduling",
            "opensprite.modules.session_commands",
            "opensprite.core.logging",
        ),
    )

    assert violations == []


def test_tools_module_does_not_import_agent_runtime():
    violations = _find_forbidden_imports(TOOLS_MODULE_ROOT, "opensprite.app.agent")
    assert violations == [], f"tools module must not import agent runtime: {violations}"


def test_removed_root_tools_package_and_imports_do_not_return():
    legacy_module = "opensprite.tools"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert not TOOLS_ROOT.exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_removed_root_agent_package_and_imports_do_not_return():
    legacy_module = "opensprite.agent"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert not (OPENSPRITE_ROOT / "agent").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_core_contracts_do_not_import_ports_or_outer_packages():
    violations = _find_imports_outside(CORE_CONTRACTS_ROOT, ("opensprite.core.contracts",))
    assert violations == [], f"core contracts must remain framework-independent: {violations}"


def test_channel_identity_contracts_have_one_canonical_owner_and_no_channel_alias():
    symbols = {
        "normalize_identifier",
        "build_session_id",
        "external_chat_id_from_session",
        "channel_from_session",
        "ChannelIdentity",
    }
    expected_path = Path("core/contracts/channel_identity.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.channels.identity"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "identity.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "core" / "contracts" / "test_channel_identity.py").is_file()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert violations == []


def test_channel_catalog_symbols_have_one_canonical_owner_and_no_registry_reexports():
    symbols = {
        "ChannelTypeSpec",
        "CHANNEL_TYPES",
        "get_channel_type",
        "list_connectable_channel_types",
        "default_instance_config",
        "make_unique_instance_id",
    }
    expected_path = Path("modules/channels/catalog.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body:
            if isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.channels.registry"
    violations = [
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            (legacy_module,),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            (legacy_module,),
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "registry.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    canonical_owner = OPENSPRITE_ROOT / expected_path
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        if module_path != canonical_owner:
            assert symbols.isdisjoint(_top_level_bound_names(module_path))
    assert sorted(set(violations)) == []


def test_channel_catalog_only_imports_pure_configuration_and_core_contracts():
    violations = _find_imports_outside(
        CHANNELS_MODULE_ROOT / "catalog.py",
        (
            "opensprite.config.channel_instances",
            "opensprite.core.contracts.channel_identity",
            "opensprite.modules.channels",
        ),
    )

    assert violations == [], f"channel catalog must remain runtime-independent: {violations}"


def test_channel_settings_symbols_have_one_canonical_owner_and_no_legacy_module():
    symbols = {
        "ChannelSettingsError",
        "ChannelSettingsValidationError",
        "ChannelSettingsNotFound",
        "ChannelSettingsService",
        "FIXED_CHANNEL_INSTANCES",
    }
    expected_path = Path("modules/channels/settings.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body:
            if isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.channels.settings"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            (legacy_module,),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            (legacy_module,),
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "settings.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    canonical_owner = OPENSPRITE_ROOT / expected_path
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        if module_path != canonical_owner:
            assert symbols.isdisjoint(_top_level_bound_names(module_path))
    assert sorted(set(violations)) == []


def test_channel_settings_only_imports_configuration_and_core_dependencies():
    violations = _find_imports_outside(
        CHANNELS_MODULE_ROOT / "settings.py",
        (
            "opensprite.config.channel_instances",
            "opensprite.config.defaults",
            "opensprite.config.json_files",
            "opensprite.config.schema",
            "opensprite.core.contracts.channel_identity",
            "opensprite.modules.channels",
        ),
    )

    assert violations == [], f"channel settings must remain runtime-independent: {violations}"


def test_channel_runtime_symbols_have_one_canonical_application_owner():
    symbols = {
        "CHANNEL_FACTORIES",
        "FIXED_RUNTIME_INSTANCES",
        "ChannelRuntimeManager",
        "start_channels",
    }
    expected_path = Path("app/channels/runtime.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body:
            if isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_source = "opensprite.channels"
    violations = [
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            (legacy_source,),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            (legacy_source,),
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_source,
            symbols,
            include_submodules=False,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_source,
            symbols,
            include_submodules=False,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    canonical_owner = OPENSPRITE_ROOT / expected_path
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        if module_path != canonical_owner:
            assert symbols.isdisjoint(_top_level_bound_names(module_path))
    assert sorted(set(violations)) == []


def test_channel_runtime_only_imports_application_composition_dependencies():
    violations = _find_imports_outside(
        APP_CHANNELS_ROOT / "runtime.py",
        (
            "opensprite.app.channels",
            "opensprite.config.channel_instances",
            "opensprite.core.contracts.channel_identity",
            "opensprite.core.logging",
        ),
    )

    assert violations == [], f"channel runtime must remain application-owned: {violations}"


def test_channel_adapter_factory_symbols_have_one_canonical_application_owner():
    symbols = {
        "AdapterFactory",
        "CHANNEL_ADAPTER_FACTORIES",
        "build_channel_adapter",
    }
    expected_path = Path("app/channels/adapters.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body:
            if isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.channels.registry"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_symbols_imports_or_access(
            OPENSPRITE_ROOT,
            (legacy_module,),
            symbols,
        ),
        *_find_forbidden_symbols_imports_or_access(
            TESTS_ROOT,
            (legacy_module,),
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            OPENSPRITE_ROOT,
            legacy_module,
            symbols,
        ),
        *_find_forbidden_dynamic_module_or_symbols_access(
            TESTS_ROOT,
            legacy_module,
            symbols,
        ),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CHANNELS_ROOT / "registry.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    canonical_owner = OPENSPRITE_ROOT / expected_path
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        if module_path != canonical_owner:
            assert symbols.isdisjoint(_top_level_bound_names(module_path))
    assert sorted(set(violations)) == []


def test_channel_adapter_factory_only_imports_composition_dependencies():
    violations = _find_imports_outside(
        APP_CHANNELS_ROOT / "adapters.py",
        (
            "opensprite.app.channels",
            "opensprite.core.contracts.channel_identity",
            "opensprite.integrations.channels.telegram",
            "opensprite.integrations.web.adapter",
        ),
    )

    assert violations == [], f"channel adapter factories must remain application-owned: {violations}"


def test_execution_event_contracts_have_one_canonical_owner_and_no_agent_alias():
    symbols = {
        "LLM_STEP_COMPLETED_STATUS",
        "LLM_STEP_ERROR_STATUS",
        "COMPACTED_CONVERSATION_STATE_HEADING",
        "COMPACTED_EXECUTION_STATE_HEADING",
        "COMPACTION_HANDOFF_HEADINGS",
        "LLM_COMPACTION_TOO_LARGE_REASON",
        "LLM_COMPACTION_CONFIG_MISSING_REASON",
        "LLM_COMPACTION_NO_BODY_REASON",
        "LLM_COMPACTION_NO_PROMPT_REASON",
        "LLM_COMPACTION_ERROR_REASON",
        "LLM_COMPACTION_EMPTY_REASON",
        "MAX_TOOL_ITERATIONS_STOP_REASON",
        "is_max_tool_iterations_stop_reason",
        "contains_compaction_handoff",
        "format_repeated_invalid_tool_call_content",
        "ContextCompactionEvent",
        "LlmStepEvent",
    }
    expected_path = Path("core/contracts/execution_events.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.app.agent.execution_support.events"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (AGENT_EXECUTION_SUPPORT_ROOT / "events.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "core" / "contracts" / "test_execution_events.py").is_file()
    assert not (TESTS_ROOT / "agent" / "test_context_compaction_policy.py").exists()
    assert not (TESTS_ROOT / "agent" / "test_execution_fallback_policy.py").exists()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert violations == []


def test_tool_result_contracts_have_one_canonical_owner_and_no_reexports():
    symbols = {
        "ToolResultStatus",
        "tool_error_result",
        "classify_tool_result_status",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("core/contracts/tool_results.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.core.contracts.tool_results"
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)


def test_llm_contracts_have_one_canonical_owner_and_no_legacy_reexports():
    symbols = {
        "CHAT_ROLE_SYSTEM",
        "CHAT_ROLE_USER",
        "CHAT_ROLE_ASSISTANT",
        "CHAT_ROLE_TOOL",
        "CHAT_CONTENT_TYPE_TEXT",
        "CHAT_CONTENT_TYPE_IMAGE_URL",
        "ToolCall",
        "LLMResponse",
        "ChatMessage",
        "ToolDefinition",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("core/contracts/llm.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.core.contracts.llm"
    legacy_source_modules = (
        "opensprite",
        "opensprite.llms",
        "opensprite.llms.base",
    )
    violations: list[str] = []
    for symbol in symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                legacy_source_modules,
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                legacy_source_modules,
                symbol,
            )
        )

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)
    legacy_base_path = OPENSPRITE_ROOT / "llms" / "base.py"
    assert not legacy_base_path.exists()
    assert (TESTS_ROOT / "core" / "contracts" / "test_llm.py").is_file()
    assert violations == []


def test_llm_provider_port_has_one_canonical_owner_and_no_legacy_reexports():
    symbol = "LLMProvider"
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == symbol
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/ports/llm.py")]

    canonical_module = "opensprite.core.ports.llm"
    legacy_source_modules = (
        "opensprite",
        "opensprite.llms",
        "opensprite.llms.base",
    )
    violations = [
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_source_modules,
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            legacy_source_modules,
            symbol,
        ),
    ]

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})
    legacy_base_path = OPENSPRITE_ROOT / "llms" / "base.py"
    assert not legacy_base_path.exists()
    assert (TESTS_ROOT / "core" / "ports" / "test_llm_port.py").is_file()
    assert violations == []


def test_llm_fallback_has_one_app_owner_and_legacy_base_symbols_do_not_return():
    canonical_symbol = "UnconfiguredLLM"
    removed_symbols = {
        "DefaultModelProviderMixin",
        "is_unconfigured_llm",
        "UNCONFIGURED_LLM_MODEL",
    }
    symbols = {canonical_symbol, *removed_symbols}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    assert owners[canonical_symbol] == [Path("app/llm_fallback.py")]
    assert all(owners[symbol] == [] for symbol in removed_symbols)

    legacy_source_modules = (
        "opensprite",
        "opensprite.llms",
        "opensprite.llms.base",
    )
    violations: list[str] = []
    for symbol in symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                legacy_source_modules,
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                legacy_source_modules,
                symbol,
            )
        )

    llms_root = OPENSPRITE_ROOT / "llms"
    legacy_exporters = [OPENSPRITE_ROOT / "__init__.py", *sorted(llms_root.rglob("*.py"))]
    canonical_module = "opensprite.app.llm_fallback"
    for exporter in legacy_exporters:
        bound_names = _top_level_bound_names(exporter)
        assert symbols.isdisjoint(bound_names)
        assert "__getattr__" not in bound_names
        assert symbols.isdisjoint(_explicit_all_names(exporter))
        assert not _imports_symbols_or_star_from(exporter, canonical_module, symbols)

    provider_classes = {
        INTEGRATIONS_ROOT / "llm" / "openai" / "chat.py": "OpenAILLM",
        INTEGRATIONS_ROOT / "llm" / "openai" / "responses.py": "OpenAIResponsesLLM",
        INTEGRATIONS_ROOT / "llm" / "openrouter" / "chat.py": "OpenRouterLLM",
        INTEGRATIONS_ROOT / "llm" / "minimax" / "chat.py": "MiniMaxLLM",
    }
    for module_path, class_name in provider_classes.items():
        assert "get_default_model" in _class_bound_names(module_path, class_name)

    assert not (llms_root / "base.py").exists()
    assert not (TESTS_ROOT / "llms" / "test_base.py").exists()
    assert not (TESTS_ROOT / "test_runtime_unconfigured_llm.py").exists()
    assert (TESTS_ROOT / "app" / "test_llm_fallback.py").is_file()
    assert (TESTS_ROOT / "app" / "test_llm_fallback_runtime.py").is_file()
    assert (TESTS_ROOT / "integrations" / "llm" / "test_provider_default_models.py").is_file()
    assert violations == []


def test_legacy_llm_exporter_guard_detects_dynamic_module_facade(tmp_path):
    exporter = tmp_path / "__init__.py"
    exporter.write_text(
        "def __getattr__(name):\n"
        "    if name == 'UnconfiguredLLM':\n"
        "        from opensprite.app.llm_fallback import UnconfiguredLLM\n"
        "        return UnconfiguredLLM\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )

    assert "__getattr__" in _top_level_bound_names(exporter)


def test_provider_retry_policy_has_one_run_module_owner_and_no_legacy_llm_path():
    symbols = {
        "RetryDelay",
        "retry_delay_from_error",
        "looks_like_transient_transport_error",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in symbols:
                    owners[node.name].append(relative_path)

    expected_path = Path("modules/runs/provider_retry.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    legacy_module = "opensprite.llms.retry"
    legacy_sources = ("opensprite.llms", legacy_module)
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_dynamic_module_or_symbol_access(
            OPENSPRITE_ROOT,
            legacy_module,
            "retry_delay_from_error",
        ),
        *_find_forbidden_dynamic_module_or_symbol_access(
            TESTS_ROOT,
            legacy_module,
            "retry_delay_from_error",
        ),
    ]
    for symbol in symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                legacy_sources,
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                legacy_sources,
                symbol,
            )
        )

    assert not (OPENSPRITE_ROOT / "llms" / "retry.py").exists()
    assert not (TESTS_ROOT / "llms" / "test_retry.py").exists()
    assert (TESTS_ROOT / "modules" / "runs" / "test_provider_retry.py").is_file()
    assert violations == []


def test_subagent_model_routing_has_one_canonical_owner_and_no_legacy_reexports():
    symbol = "ModelRoutedProvider"
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == symbol
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("modules/subagents/model_routing.py")]
    llms_root = OPENSPRITE_ROOT / "llms"
    legacy_module = "opensprite.llms.routed"
    legacy_source_modules = (
        "opensprite",
        "opensprite.llms",
        legacy_module,
    )
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            legacy_source_modules,
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            legacy_source_modules,
            symbol,
        ),
    ]

    legacy_exporters = [OPENSPRITE_ROOT / "__init__.py", *sorted(llms_root.rglob("*.py"))]
    canonical_module = "opensprite.modules.subagents.model_routing"
    for exporter in legacy_exporters:
        assert symbol not in _top_level_bound_names(exporter)
        assert symbol not in _explicit_all_names(exporter)
        assert not _imports_symbols_or_star_from(exporter, canonical_module, {symbol})

    assert not (llms_root / "routed.py").exists()
    assert "opensprite.llms" in legacy_source_modules
    assert (TESTS_ROOT / "modules" / "subagents" / "test_model_routing.py").is_file()
    assert violations == []


def test_legacy_tool_result_status_module_does_not_return():
    legacy_module = "opensprite.tools.result_status"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (TOOLS_ROOT / "result_status.py").exists()
    assert not (TESTS_ROOT / "tools" / "test_result_status.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_core_ports_only_import_core_contracts():
    violations = _find_imports_outside(CORE_PORTS_ROOT, ("opensprite.core.contracts",))
    assert violations == [], f"core ports may only depend on core contracts: {violations}"


def test_context_builder_port_has_one_canonical_owner():
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == "ContextBuilder" for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/ports/context.py")]


def test_prompt_history_contract_has_one_canonical_owner_and_no_reexports():
    symbol = "PreparedPromptHistory"
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == symbol for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/contracts/prompt_history.py")]

    canonical_module = "opensprite.core.contracts.prompt_history"
    legacy_module_name = "opensprite.context.message_history"
    legacy_module_path = CONTEXT_ROOT / "message_history.py"
    assert not legacy_module_path.exists()

    history_module = CONVERSATIONS_MODULE_ROOT / "history.py"
    history_tree = ast.parse(
        history_module.read_text(encoding="utf-8-sig"),
        filename=str(history_module),
    )
    history_imports = [
        (alias.name, alias.asname)
        for node in history_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(history_module, node) == canonical_module
        for alias in node.names
        if alias.name == symbol
    ]
    assert history_imports == [(symbol, "_PreparedPromptHistory")]

    for consumer in (
        AGENT_ROOT / "agent.py",
        AGENT_EXECUTION_SUPPORT_ROOT / "llm_calls.py",
    ):
        assert _imports_all_symbols_from_without_aliases(
            consumer,
            canonical_module,
            {symbol},
        )
        assert not _imports_symbols_or_star_from(
            consumer,
            legacy_module_name,
            {symbol, "_PreparedPromptHistory"},
        )
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})


def test_message_history_service_has_one_canonical_owner_and_no_reexports():
    symbol = "MessageHistoryService"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/conversations/history.py")]

    canonical_module = "opensprite.modules.conversations.history"
    legacy_module = "opensprite.context.message_history"
    legacy_path = CONTEXT_ROOT / "message_history.py"
    assert not legacy_path.exists()

    agent_module = AGENT_ROOT / "agent.py"
    agent_tree = ast.parse(
        agent_module.read_text(encoding="utf-8-sig"),
        filename=str(agent_module),
    )
    agent_imports = [
        (alias.name, alias.asname)
        for node in agent_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(agent_module, node) == canonical_module
        for alias in node.names
        if alias.name == symbol
    ]
    assert agent_imports == [(symbol, "_MessageHistoryService")]

    legacy_imports = [
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            (legacy_module,),
            symbol,
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            (legacy_module,),
            symbol,
        ),
    ]
    assert legacy_imports == []

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})
    assert _top_level_bound_names(CONVERSATIONS_MODULE_ROOT / "__init__.py") == set()
    assert (TESTS_ROOT / "modules" / "conversations" / "test_history.py").is_file()
    assert not (TESTS_ROOT / "llms" / "test_message_history_reasoning.py").exists()


def test_message_history_service_dependency_direction_is_explicit():
    module_path = CONVERSATIONS_MODULE_ROOT / "history.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.core.contracts",
        "opensprite.core.ports",
        "opensprite.llms",
        "opensprite.core.logging",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []
    assert not _find_forbidden_imports(CONTEXT_ROOT, "opensprite.modules.conversations")


def test_history_reset_service_has_one_canonical_owner_and_no_reexports():
    symbol = "HistoryResetService"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/conversations/reset.py")]

    canonical_module = "opensprite.modules.conversations.reset"
    agent_module = AGENT_ROOT / "agent.py"
    agent_tree = ast.parse(
        agent_module.read_text(encoding="utf-8-sig"),
        filename=str(agent_module),
    )
    agent_imports = [
        (alias.name, alias.asname)
        for node in agent_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(agent_module, node) == canonical_module
        for alias in node.names
        if alias.name == symbol
    ]
    assert agent_imports == [(symbol, "_HistoryResetService")]

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})
    assert _top_level_bound_names(CONVERSATIONS_MODULE_ROOT / "__init__.py") == set()
    assert (TESTS_ROOT / "modules" / "conversations" / "test_reset.py").is_file()
    assert not (TESTS_ROOT / "context" / "test_history_reset.py").exists()


def test_history_reset_service_dependency_direction_is_explicit():
    module_path = CONVERSATIONS_MODULE_ROOT / "reset.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.core.ports",
        "opensprite.core.logging",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_context_message_history_module_does_not_return():
    legacy_module = "opensprite.context.message_history"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            ("opensprite.context", legacy_module),
            "HistoryResetService",
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            ("opensprite.context", legacy_module),
            "HistoryResetService",
        ),
    ]

    assert not (CONTEXT_ROOT / "message_history.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_workspace_instruction_policy_has_one_canonical_owner_and_no_reexports():
    symbols = {
        "WORKSPACE_INSTRUCTION_MAX_CHARS",
        "WORKSPACE_INSTRUCTION_TRUNCATE_HEAD_RATIO",
        "WORKSPACE_INSTRUCTION_TRUNCATE_TAIL_RATIO",
        "find_workspace_instruction_threats",
        "sanitize_workspace_instruction",
        "truncate_workspace_instruction",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    expected_path = Path("modules/workspace/instructions.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.modules.workspace.instructions"
    file_builder = CONTEXT_INTEGRATION_ROOT / "file_builder.py"
    file_builder_tree = ast.parse(
        file_builder.read_text(encoding="utf-8-sig"),
        filename=str(file_builder),
    )
    sanitizer_imports = [
        (alias.name, alias.asname)
        for node in file_builder_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(file_builder, node) == canonical_module
        for alias in node.names
    ]
    assert sanitizer_imports == [
        ("sanitize_workspace_instruction", "_sanitize_workspace_instruction")
    ]

    filesystem_adapter = APP_WORKSPACE_TOOLS_ROOT / "filesystem.py"
    filesystem_tree = ast.parse(
        filesystem_adapter.read_text(encoding="utf-8-sig"),
        filename=str(filesystem_adapter),
    )
    filesystem_sanitizer_imports = [
        (alias.name, alias.asname)
        for node in filesystem_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(filesystem_adapter, node) == canonical_module
        for alias in node.names
    ]
    assert filesystem_sanitizer_imports == [
        ("sanitize_workspace_instruction", "_sanitize_workspace_instruction")
    ]

    file_builder_class = next(
        node
        for node in file_builder_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FileContextBuilder"
    )
    legacy_member_names = {
        node.name
        for node in file_builder_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in file_builder_class.body:
        if isinstance(node, ast.Assign):
            legacy_member_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            legacy_member_names.add(node.target.id)
    assert {
        "CONTEXT_FILE_MAX_CHARS",
        "CONTEXT_TRUNCATE_HEAD_RATIO",
        "CONTEXT_TRUNCATE_TAIL_RATIO",
        "_CONTEXT_INVISIBLE_CHARS",
        "_CONTEXT_THREAT_PATTERNS",
        "_sanitize_context_file_content",
        "_context_file_findings",
        "_truncate_context_file_content",
    }.isdisjoint(legacy_member_names)

    filesystem_legacy_names = {
        node.name
        for node in filesystem_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in filesystem_tree.body:
        if isinstance(node, ast.Assign):
            filesystem_legacy_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            filesystem_legacy_names.add(node.target.id)
    assert {
        "_CONTEXT_INVISIBLE_CHARS",
        "_CONTEXT_THREAT_PATTERNS",
        "_context_file_findings",
        "_truncate_agent_hint",
        "_sanitize_agent_hint",
    }.isdisjoint(filesystem_legacy_names)

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)
    assert _top_level_bound_names(WORKSPACE_MODULE_ROOT / "__init__.py") == set()
    assert (TESTS_ROOT / "modules" / "workspace" / "test_instructions.py").is_file()
    assert (TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_navigation.py").is_file()


def test_workspace_instruction_policy_only_imports_standard_library():
    module_path = WORKSPACE_MODULE_ROOT / "instructions.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_prompt_memory_context_symbols_have_one_canonical_owner_and_no_reexports():
    symbols = {"PromptMemoryDocument", "PromptMemoryDocumentService"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("modules/documents/prompt_context.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.modules.documents.prompt_context"
    legacy_module = CONTEXT_ROOT / "message_history.py"
    assert not legacy_module.exists()

    file_builder = CONTEXT_INTEGRATION_ROOT / "file_builder.py"
    assert symbols.isdisjoint(_top_level_bound_names(file_builder))
    file_builder_tree = ast.parse(
        file_builder.read_text(encoding="utf-8-sig"),
        filename=str(file_builder),
    )
    service_imports = [
        (alias.name, alias.asname)
        for node in file_builder_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(file_builder, node) == canonical_module
        for alias in node.names
        if alias.name == "PromptMemoryDocumentService"
    ]
    assert service_imports == [
        ("PromptMemoryDocumentService", "_PromptMemoryDocumentService")
    ]

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)
    assert (TESTS_ROOT / "modules" / "documents" / "test_prompt_context.py").is_file()


def test_prompt_memory_context_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "prompt_context.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_relevant_learning_context_has_one_canonical_owner_and_no_reexports():
    symbol = "RelevantLearningContextService"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/documents/learning.py")]

    canonical_module = "opensprite.modules.documents.learning"
    legacy_module = CONTEXT_ROOT / "message_history.py"
    assert not legacy_module.exists()

    file_builder = CONTEXT_INTEGRATION_ROOT / "file_builder.py"
    file_builder_tree = ast.parse(
        file_builder.read_text(encoding="utf-8-sig"),
        filename=str(file_builder),
    )
    service_imports = [
        (alias.name, alias.asname)
        for node in file_builder_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(file_builder, node) == canonical_module
        for alias in node.names
        if alias.name == symbol
    ]
    assert service_imports == [(symbol, "_RelevantLearningContextService")]

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})
    assert (TESTS_ROOT / "modules" / "documents" / "test_learning.py").is_file()
    assert not (TESTS_ROOT / "context" / "test_prompt_memory_documents.py").exists()


def test_learning_ledger_has_one_canonical_owner_and_no_reexports():
    symbol = "LearningLedger"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/documents/learning.py")]

    canonical_module = "opensprite.modules.documents.learning"
    legacy_module = "opensprite.context.message_history"
    legacy_path = CONTEXT_ROOT / "message_history.py"
    assert not legacy_path.exists()

    consumers = (
        AGENT_ROOT / "agent.py",
        AGENT_ROOT / "agent_run_hooks.py",
        CONTEXT_INTEGRATION_ROOT / "file_builder.py",
    )
    for consumer in consumers:
        tree = ast.parse(consumer.read_text(encoding="utf-8-sig"), filename=str(consumer))
        imports = [
            (alias.name, alias.asname)
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and _resolved_import(consumer, node) == canonical_module
            for alias in node.names
            if alias.name == symbol
        ]
        assert imports == [(symbol, "_LearningLedger")]

    legacy_test_imports = [
        test_path.relative_to(PROJECT_ROOT)
        for test_path in sorted(TESTS_ROOT.rglob("*.py"))
        if _imports_symbols_or_star_from(test_path, legacy_module, {symbol})
    ]
    assert legacy_test_imports == []

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})
    assert (TESTS_ROOT / "modules" / "documents" / "test_learning_ledger_policy.py").is_file()


def test_learning_module_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "learning.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_json_learning_ledger_store_has_one_canonical_owner_and_no_reexports():
    symbol = "JsonLearningLedgerStore"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/documents/learning.py")]

    canonical_module = "opensprite.integrations.documents.learning"
    agent_module = AGENT_ROOT / "agent.py"
    agent_tree = ast.parse(
        agent_module.read_text(encoding="utf-8-sig"),
        filename=str(agent_module),
    )
    adapter_imports = [
        (alias.name, alias.asname)
        for node in agent_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(agent_module, node) == canonical_module
        for alias in node.names
        if alias.name == symbol
    ]
    assert adapter_imports == [(symbol, "_JsonLearningLedgerStore")]

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})
    assert (TESTS_ROOT / "integrations" / "documents" / "test_learning_store.py").is_file()


def test_json_learning_ledger_store_only_depends_on_logging_and_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "learning.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if imported_module == "opensprite.core.logging" or imported_module.startswith(
                "opensprite.core.logging."
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []
    for policy_root in (
        CONTEXT_INTEGRATION_ROOT,
        DOCUMENTS_MODULE_ROOT,
    ):
        assert not _find_forbidden_imports(
            policy_root,
            "opensprite.integrations.documents.learning",
        )


def test_legacy_context_builder_module_and_facade_do_not_return():
    legacy_module = "opensprite.context.builder"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    context_initializer = OPENSPRITE_ROOT / "context" / "__init__.py"
    assert not context_initializer.exists()
    assert not (OPENSPRITE_ROOT / "context" / "builder.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_file_context_builder_has_one_canonical_owner_and_no_legacy_module():
    symbol = "FileContextBuilder"
    canonical_module = "opensprite.integrations.context.file_builder"
    canonical_path = CONTEXT_INTEGRATION_ROOT / "file_builder.py"
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]
    legacy_module = "opensprite.context.file_builder"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert owners == [Path("integrations/context/file_builder.py")]
    assert not (CONTEXT_ROOT / "file_builder.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert _top_level_bound_names(CONTEXT_INTEGRATION_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbol not in _top_level_bound_names(initializer)
        assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})

    builder_tree = ast.parse(
        canonical_path.read_text(encoding="utf-8-sig"),
        filename=str(canonical_path),
    )
    builder_class = next(
        node
        for node in builder_tree.body
        if isinstance(node, ast.ClassDef) and node.name == symbol
    )
    builder_methods = {
        node.name
        for node in builder_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    port_path = CORE_PORTS_ROOT / "context.py"
    port_tree = ast.parse(
        port_path.read_text(encoding="utf-8-sig"),
        filename=str(port_path),
    )
    port_class = next(
        node
        for node in port_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ContextBuilder"
    )
    port_methods = {
        node.name
        for node in port_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert port_methods == {
        "add_assistant_message",
        "add_tool_result",
        "build_messages",
        "build_system_prompt",
    }
    assert port_methods <= builder_methods

    assert not list((TESTS_ROOT / "context").glob("test_file_builder*.py"))
    assert not (TESTS_ROOT / "context" / "test_recent_summary_builder.py").exists()
    assert (TESTS_ROOT / "integrations" / "context" / "test_file_builder_direct_context.py").is_file()
    assert (TESTS_ROOT / "integrations" / "context" / "test_recent_summary_builder.py").is_file()
    assert violations == []


def test_file_context_adapter_dependencies_stay_explicit():
    violations = _find_imports_outside(
        CONTEXT_INTEGRATION_ROOT,
        (
            "opensprite.integrations.workspace.paths",
            "opensprite.core.contracts.runtime_context",
            "opensprite.integrations.documents",
            "opensprite.integrations.subagents",
            "opensprite.integrations.workspace.bootstrap",
            "opensprite.modules.documents",
            "opensprite.modules.skills.loader",
            "opensprite.modules.workspace.instructions",
        ),
    )

    assert violations == []


def test_runtime_context_contract_has_one_canonical_owner():
    owners: dict[str, list[Path]] = {
        "RUNTIME_CONTEXT_TAG": [],
        "build_runtime_context": [],
    }
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "build_runtime_context":
                owners[node.name].append(relative_path)
            if isinstance(node, ast.Assign):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            else:
                names = []
            if "RUNTIME_CONTEXT_TAG" in names:
                owners["RUNTIME_CONTEXT_TAG"].append(relative_path)

    expected_path = Path("core/contracts/runtime_context.py")
    assert owners == {symbol: [expected_path] for symbol in owners}


def test_legacy_context_runtime_module_does_not_return():
    legacy_module = "opensprite.context.runtime"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "context" / "runtime.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_session_identity_policy_has_one_canonical_owner_and_no_reexports():
    symbols = {"sanitize_path_segment", "split_session_id"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("core/session_identity.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.core.session_identity"
    paths_module = WORKSPACE_INTEGRATION_ROOT / "paths.py"
    paths_tree = ast.parse(
        paths_module.read_text(encoding="utf-8-sig"),
        filename=str(paths_module),
    )
    paths_imports = [
        (alias.name, alias.asname)
        for node in paths_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(paths_module, node) == canonical_module
        for alias in node.names
    ]
    assert paths_imports == [
        ("sanitize_path_segment", "_sanitize_path_segment"),
        ("split_session_id", "_split_session_id"),
    ]
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"split_session_id", "_sanitize_path_segment"}
        for node in paths_tree.body
    )
    assert "split_session_id" not in _top_level_bound_names(paths_module)

    scheduling_module = APP_ROOT / "scheduling.py"
    scheduling_tree = ast.parse(
        scheduling_module.read_text(encoding="utf-8-sig"),
        filename=str(scheduling_module),
    )
    scheduling_imports = [
        (alias.name, alias.asname)
        for node in scheduling_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(scheduling_module, node) == canonical_module
        for alias in node.names
        if alias.name == "split_session_id"
    ]
    assert scheduling_imports == [("split_session_id", None)]

    legacy_module = "opensprite.context.paths"
    legacy_imports = [
        *_find_forbidden_symbol_imports_or_access(
            OPENSPRITE_ROOT,
            (legacy_module,),
            "split_session_id",
        ),
        *_find_forbidden_symbol_imports_or_access(
            TESTS_ROOT,
            (legacy_module,),
            "split_session_id",
        ),
    ]
    assert legacy_imports == []

    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)
    assert (TESTS_ROOT / "core" / "test_session_identity.py").is_file()


def test_session_identity_policy_only_imports_standard_library():
    module_path = CORE_ROOT / "session_identity.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_url_composition_helper_has_one_canonical_owner():
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "join_url_path"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/url.py")]


def test_legacy_utils_url_module_does_not_return():
    legacy_module = "opensprite.utils.url"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "utils" / "url.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_media_provider_ports_have_one_canonical_owner():
    symbols = {"ImageAnalysisProvider", "SpeechToTextProvider", "VideoAnalysisProvider"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in symbols:
                owners[node.name].append(relative_path)

    expected_path = Path("core/ports/media.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_media_base_module_and_provider_reexports_do_not_return():
    symbols = {"ImageAnalysisProvider", "SpeechToTextProvider", "VideoAnalysisProvider"}
    legacy_module = "opensprite.media.base"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "base.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_media_router_has_one_canonical_owner():
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == "MediaRouter" for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("modules/media/router.py")]


def test_media_modules_only_import_core_or_sibling_modules():
    violations = _find_imports_outside(
        MEDIA_MODULE_ROOT,
        ("opensprite.core", "opensprite.modules.media"),
    )
    assert violations == [], f"media modules must remain provider-neutral: {violations}"


def test_legacy_media_router_module_and_reexport_do_not_return():
    legacy_module = "opensprite.media.router"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "router.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_audio_input_preprocessing_has_one_canonical_owner_and_no_reexports():
    symbols = {
        "PreparedAudioTurnInput",
        "AudioInputPreprocessResult",
        "AudioInputPreprocessor",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("modules/media/audio_input.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.modules.media.audio_input"
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)


def test_legacy_media_audio_input_module_does_not_return():
    legacy_module = "opensprite.media.audio_input"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "audio_input.py").exists()
    assert not (TESTS_ROOT / "agent" / "test_audio_input.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_inbound_media_policy_has_one_canonical_owner_and_no_reexports():
    symbols = {
        "INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON",
        "INBOUND_IMAGE_EXTENSIONS",
        "INBOUND_AUDIO_EXTENSIONS",
        "INBOUND_VIDEO_EXTENSIONS",
        "decode_data_url",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/media/inbound.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert "decode_data_url" not in _class_bound_names(
        MEDIA_PERSISTENCE_MODULE,
        "InboundMediaPersistence",
    )

    canonical_module = "opensprite.modules.media.inbound"
    assert _imports_all_symbols_from_without_aliases(
        MEDIA_PERSISTENCE_MODULE,
        canonical_module,
        {"INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON", "decode_data_url"},
    )
    assert _imports_all_symbols_from_without_aliases(
        AGENT_ROOT / "turn_input.py",
        canonical_module,
        {
            "INBOUND_IMAGE_EXTENSIONS",
            "INBOUND_AUDIO_EXTENSIONS",
            "INBOUND_VIDEO_EXTENSIONS",
        },
    )
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)

    legacy_imports = []
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if _imports_symbols_or_star_from(module_path, "opensprite.media", symbols):
                legacy_imports.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (TESTS_ROOT / "agent" / "test_media_inbound_policy.py").exists()
    assert legacy_imports == []

    assert _class_bound_names(MEDIA_PERSISTENCE_MODULE, "InboundMediaPersistence") == {
        "__init__",
        "persist_inbound_media_with_events",
    }


def test_media_persistence_integration_has_one_canonical_owner():
    symbols = {"InboundMediaPersistResult", "InboundMediaPersistence"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    legacy_bindings: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)
        bound_names = _top_level_bound_names(module_path)
        if "AgentMediaService" in bound_names:
            legacy_bindings.append(relative_path)

    expected_path = Path("integrations/persistence/media.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert legacy_bindings == []

    canonical_module = "opensprite.integrations.persistence.media"
    for consumer in (AGENT_ROOT / "agent.py", AGENT_ROOT / "turn_input.py"):
        assert _imports_all_symbols_from_without_aliases(
            consumer,
            canonical_module,
            {"InboundMediaPersistence"},
        )
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)

    assert _find_forbidden_imports(PERSISTENCE_INTEGRATION_ROOT, "opensprite.context") == []


def test_legacy_media_package_does_not_return():
    legacy_module = "opensprite.media"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not MEDIA_ROOT.exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_media_turn_policy_has_canonical_owners_and_no_reexports():
    symbols = {
        "MEDIA_ONLY_HISTORY_MARKER",
        "MEDIA_ONLY_HISTORY_FAILURE_MARKER",
        "MEDIA_ONLY_HISTORY_PARTIAL_FAILURE_MARKER",
        "is_media_only_message",
        "format_saved_media_history_content",
        "format_failed_media_history_content",
        "format_partially_saved_media_history_content",
        "augment_message_for_media",
    }
    unique_symbols = symbols - {"augment_message_for_media"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in unique_symbols}
    augmentation_owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in unique_symbols & declared_names:
                owners[name].append(relative_path)
            if "augment_message_for_media" in declared_names:
                augmentation_owners.append(relative_path)

    expected_path = Path("modules/media/turn_policy.py")
    assert owners == {symbol: [expected_path] for symbol in unique_symbols}
    assert augmentation_owners == [Path("app/agent/media_runtime.py"), expected_path]
    assert symbols <= _top_level_bound_names(MEDIA_MODULE_ROOT / "turn_policy.py")

    service_bindings = _class_bound_names(
        MEDIA_PERSISTENCE_MODULE,
        "InboundMediaPersistence",
    )
    assert symbols.isdisjoint(service_bindings)

    canonical_module = "opensprite.modules.media.turn_policy"
    assert _imports_all_symbols_from_without_aliases(
        AGENT_ROOT / "turn_runner.py",
        canonical_module,
        {
            "is_media_only_message",
            "format_saved_media_history_content",
            "format_failed_media_history_content",
            "format_partially_saved_media_history_content",
        },
    )
    media_runtime_path = AGENT_ROOT / "media_runtime.py"
    media_runtime_tree = ast.parse(
        media_runtime_path.read_text(encoding="utf-8-sig"),
        filename=str(media_runtime_path),
    )
    media_runtime_policy_imports = [
        (alias.name, alias.asname)
        for node in media_runtime_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(media_runtime_path, node) == canonical_module
        for alias in node.names
    ]
    assert media_runtime_policy_imports == [
        ("augment_message_for_media", "_augment_message_for_media")
    ]
    assert _find_forbidden_imports(PERSISTENCE_INTEGRATION_ROOT, canonical_module) == []
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)

    legacy_imports = []
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if _imports_symbols_or_star_from(module_path, "opensprite.media", symbols):
                legacy_imports.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert legacy_imports == []


def test_outbound_media_policy_has_one_canonical_owner_and_no_reexports():
    symbols = {
        "OUTBOUND_MEDIA_KEYS",
        "outbound_media_error_result",
        "queue_outbound_media",
        "queued_outbound_media",
    }
    unique_symbols = symbols - {"queue_outbound_media"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in unique_symbols}
    queue_owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in unique_symbols & declared_names:
                owners[name].append(relative_path)
            if "queue_outbound_media" in declared_names:
                queue_owners.append(relative_path)

    expected_path = Path("modules/media/outbound.py")
    assert owners == {symbol: [expected_path] for symbol in unique_symbols}
    assert queue_owners == [Path("app/agent/media_runtime.py"), expected_path]
    assert symbols <= _top_level_bound_names(MEDIA_MODULE_ROOT / "outbound.py")

    service_bindings = _class_bound_names(
        MEDIA_PERSISTENCE_MODULE,
        "InboundMediaPersistence",
    )
    assert {"queue_outbound_media", "queued_outbound_media"}.isdisjoint(service_bindings)

    turn_context = AGENT_ROOT / "turn_context.py"
    assert _imports_all_symbols_from_without_aliases(
        turn_context,
        "opensprite.modules.media.outbound",
        {"queue_outbound_media", "queued_outbound_media"},
    )

    canonical_module = "opensprite.modules.media.outbound"
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)


def test_saved_media_resolution_has_one_module_owner_and_no_legacy_module():
    canonical_module = "opensprite.modules.media.saved_media"
    legacy_module = "opensprite.tools.saved_media"
    canonical_path = MEDIA_MODULE_ROOT / "saved_media.py"
    symbols = {
        "_saved_media_error_result",
        "load_saved_media_data_url",
        "resolve_media_items",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in owners:
                owners[node.name].append(relative_path)

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }
    expected_path = Path("modules/media/saved_media.py")

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "saved_media.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert all(
        name.partition(".")[0] in STDLIB_MODULES
        or name.startswith("opensprite.core.contracts.tool_results")
        for name in imported_modules
    )
    assert (TESTS_ROOT / "modules" / "media" / "test_saved_media.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_saved_media.py").exists()
    assert violations == []


def test_media_tool_adapters_have_one_app_owner_and_no_legacy_modules():
    expected_owners = {
        "AnalyzeImageTool": Path("app/tools/media/image.py"),
        "AnalyzeVideoTool": Path("app/tools/media/video.py"),
        "OCRImageTool": Path("app/tools/media/image.py"),
        "SendMediaTool": Path("app/tools/media/outbound_media.py"),
        "TranscribeAudioTool": Path("app/tools/media/audio.py"),
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in expected_owners}
    legacy_modules = (
        "opensprite.tools.audio",
        "opensprite.tools.image",
        "opensprite.tools.outbound_media",
        "opensprite.tools.video",
    )
    canonical_modules = (
        "opensprite.app.tools.media.audio",
        "opensprite.app.tools.media.image",
        "opensprite.app.tools.media.outbound_media",
        "opensprite.app.tools.media.video",
    )
    violations: list[str] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)

    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    assert owners == {symbol: [path] for symbol, path in expected_owners.items()}
    assert all(_find_spec_or_none(module_name) is not None for module_name in canonical_modules)
    assert all(_find_spec_or_none(module_name) is None for module_name in legacy_modules)
    assert all(not (TOOLS_ROOT / f"{module_name.rsplit('.', 1)[-1]}.py").exists() for module_name in legacy_modules)
    assert _top_level_bound_names(APP_MEDIA_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert set(expected_owners).isdisjoint(_top_level_bound_names(initializer))
    for test_name in ("audio", "image", "outbound_media", "video"):
        assert (TESTS_ROOT / "app" / "tools" / "media" / f"test_{test_name}.py").is_file()
        assert not (TESTS_ROOT / "tools" / f"test_{test_name}.py").exists()
    assert violations == []


def test_media_tool_adapters_only_import_core_and_modules():
    violations = _find_imports_outside(
        APP_MEDIA_TOOLS_ROOT,
        ("opensprite.core", "opensprite.modules"),
    )
    assert violations == [], f"media tool adapters have an invalid dependency: {violations}"


def test_memory_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.documents.memory"
    legacy_module = "opensprite.tools.memory"
    canonical_path = APP_DOCUMENT_TOOLS_ROOT / "memory.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "SaveMemoryTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "memory.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/documents/memory.py")]
    assert _top_level_bound_names(APP_DOCUMENT_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "SaveMemoryTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "documents" / "test_memory_tool.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_memory_tool.py").exists()
    assert violations == []


def test_memory_tool_adapter_only_imports_core_and_modules():
    violations = _find_imports_outside(
        APP_DOCUMENT_TOOLS_ROOT,
        ("opensprite.core", "opensprite.modules"),
    )
    assert violations == [], f"memory tool adapter has an invalid dependency: {violations}"


def test_search_history_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.search.history"
    legacy_module = "opensprite.tools.search"
    canonical_path = APP_SEARCH_TOOLS_ROOT / "history.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "SearchHistoryTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "search.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/search/history.py")]
    assert _top_level_bound_names(APP_SEARCH_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "SearchHistoryTool" not in _top_level_bound_names(initializer)
    assert (
        TESTS_ROOT / "app" / "tools" / "search" / "test_search_history_tool.py"
    ).is_file()
    assert not (TESTS_ROOT / "tools" / "test_search_history_tool.py").exists()
    assert violations == []


def test_search_history_tool_adapter_only_imports_core_and_modules():
    violations = _find_imports_outside(
        APP_SEARCH_TOOLS_ROOT,
        ("opensprite.core", "opensprite.modules"),
    )
    assert violations == [], f"search history tool adapter has an invalid dependency: {violations}"


def test_run_file_change_tool_adapters_have_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.runs.file_changes"
    legacy_module = "opensprite.tools.run_trace"
    canonical_path = APP_RUN_TOOLS_ROOT / "file_changes.py"
    symbols = {"ListRunFileChangesTool", "PreviewRunFileChangeRevertTool"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "run_trace.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    expected_owner = [Path("app/tools/runs/file_changes.py")]
    assert owners == {symbol: expected_owner for symbol in symbols}
    assert _top_level_bound_names(APP_RUN_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert (TESTS_ROOT / "app" / "tools" / "runs" / "test_run_trace.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_run_trace.py").exists()
    assert violations == []


def test_run_file_change_tool_adapters_only_import_core_and_modules():
    violations = _find_imports_outside(
        APP_RUN_TOOLS_ROOT,
        ("opensprite.core", "opensprite.modules"),
    )
    assert violations == [], f"run file-change tool adapters have an invalid dependency: {violations}"


def test_browser_tool_adapters_have_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.web.browser"
    legacy_module = "opensprite.tools.browser"
    canonical_path = APP_WEB_TOOLS_ROOT / "browser.py"
    symbols = {
        "BrowserToolBase",
        "BrowserNavigateTool",
        "BrowserSnapshotTool",
        "BrowserClickTool",
        "BrowserTypeTool",
        "BrowserPressTool",
        "BrowserScrollTool",
        "BrowserBackTool",
        "BrowserConsoleTool",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "browser.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _find_spec_or_none("opensprite.modules.tools.browser_navigation") is not None
    expected_owner = [Path("app/tools/web/browser.py")]
    assert owners == {symbol: expected_owner for symbol in symbols}
    assert "validate_navigation_url" not in _top_level_bound_names(canonical_path)
    assert _top_level_bound_names(APP_WEB_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert (TESTS_ROOT / "app" / "tools" / "web" / "test_browser.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_browser.py").exists()
    assert violations == []


def test_credential_store_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.auth.credential_store"
    legacy_module = "opensprite.tools.credential_store"
    canonical_path = APP_AUTH_TOOLS_ROOT / "credential_store.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "CredentialStoreTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "credential_store.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/auth/credential_store.py")]
    assert _top_level_bound_names(APP_AUTH_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "CredentialStoreTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "auth" / "test_credential_store.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_credential_store.py").exists()
    assert violations == []


def test_auth_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_AUTH_TOOLS_ROOT,
        ("opensprite.core", "opensprite.integrations", "opensprite.modules"),
    )
    assert violations == [], f"auth tool adapters have an invalid dependency: {violations}"


def test_configure_mcp_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.mcp.configure"
    legacy_module = "opensprite.tools.mcp_config"
    canonical_path = APP_MCP_TOOLS_ROOT / "configure.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "ConfigureMCPTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "mcp_config.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/mcp/configure.py")]
    assert _top_level_bound_names(APP_MCP_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "ConfigureMCPTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "mcp" / "test_mcp_configure.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_mcp_config.py").exists()
    assert violations == []


def test_mcp_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_MCP_TOOLS_ROOT,
        ("opensprite.config", "opensprite.core", "opensprite.modules"),
    )
    assert violations == [], f"MCP tool adapters have an invalid dependency: {violations}"


def test_process_management_tool_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.processes.management"
    legacy_module = "opensprite.tools.process"
    canonical_path = APP_PROCESS_TOOLS_ROOT / "management.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == "ProcessTool" for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "process.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/processes/management.py")]
    assert _top_level_bound_names(APP_PROCESS_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "ProcessTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "processes" / "test_process_management.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_process_tool.py").exists()
    assert violations == []


def test_exec_tool_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.processes.exec"
    legacy_module = "opensprite.tools.shell"
    canonical_path = APP_PROCESS_TOOLS_ROOT / "exec.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == "ExecTool" for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "shell.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/processes/exec.py")]
    assert _top_level_bound_names(APP_PROCESS_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "ExecTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "processes" / "test_exec.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_shell_exec_policy.py").exists()
    assert violations == []


def test_process_tool_adapter_only_imports_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_PROCESS_TOOLS_ROOT,
        ("opensprite.core", "opensprite.integrations", "opensprite.modules"),
    )
    assert violations == [], f"process tool adapters have an invalid dependency: {violations}"


def test_shell_policy_has_one_module_owner_and_exec_adapter_uses_it():
    canonical_module = "opensprite.modules.tools.shell_policy"
    canonical_path = TOOLS_MODULE_ROOT / "shell_policy.py"
    adapter_path = APP_PROCESS_TOOLS_ROOT / "exec.py"
    module_test_path = TESTS_ROOT / "modules" / "tools" / "test_shell_policy.py"
    adapter_test_path = TESTS_ROOT / "app" / "tools" / "processes" / "test_exec.py"
    policy_symbols = {
        "DEFAULT_EXEC_DENY_PATTERNS",
        "classify_destructive_shell_command",
        "dangerous_command_error",
        "foreground_exec_guidance",
        "has_shell_background_operator",
        "is_help_or_version_command",
    }
    adapter_symbols = {
        "DEFAULT_EXEC_DENY_PATTERNS",
        "classify_destructive_shell_command",
        "dangerous_command_error",
        "foreground_exec_guidance",
        "is_help_or_version_command",
    }
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8-sig"), filename=str(adapter_path))
    adapter_definitions = {
        node.name
        for node in adapter_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert canonical_path.is_file()
    assert _find_spec_or_none(canonical_module) is not None
    assert policy_symbols <= _top_level_bound_names(canonical_path)
    assert policy_symbols.isdisjoint(adapter_definitions)
    assert _imports_all_symbols_from_without_aliases(
        adapter_path,
        canonical_module,
        adapter_symbols,
    )
    assert module_test_path.is_file()
    assert _find_forbidden_imports(module_test_path, "opensprite.app") == []
    assert not _imports_symbols_or_star_from(adapter_test_path, canonical_module, policy_symbols)
    assert _find_imports_outside(canonical_path, ("opensprite.core",)) == []


def test_workspace_diagnostics_has_one_module_owner_and_filesystem_adapter_uses_it():
    canonical_module = "opensprite.modules.tools.workspace_diagnostics"
    canonical_path = TOOLS_MODULE_ROOT / "workspace_diagnostics.py"
    adapter_path = APP_WORKSPACE_TOOLS_ROOT / "filesystem.py"
    module_test_path = TESTS_ROOT / "modules" / "tools" / "test_workspace_diagnostics.py"
    adapter_test_path = TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_patch.py"
    module_symbols = {"format_post_edit_diagnostics"}
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8-sig"), filename=str(adapter_path))
    adapter_definitions = {
        node.name
        for node in adapter_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert canonical_path.is_file()
    assert _find_spec_or_none(canonical_module) is not None
    assert module_symbols <= _top_level_bound_names(canonical_path)
    assert module_symbols.isdisjoint(adapter_definitions)
    assert _imports_all_symbols_from_without_aliases(adapter_path, canonical_module, module_symbols)
    assert module_test_path.is_file()
    assert _find_forbidden_imports(module_test_path, "opensprite.app") == []
    assert not _imports_symbols_or_star_from(adapter_test_path, canonical_module, module_symbols)
    assert _find_imports_outside(canonical_path, ("yaml",)) == []


def test_workspace_write_policy_has_one_module_owner_and_filesystem_adapter_uses_it():
    canonical_module = "opensprite.modules.tools.workspace_write_policy"
    canonical_path = TOOLS_MODULE_ROOT / "workspace_write_policy.py"
    adapter_path = APP_WORKSPACE_TOOLS_ROOT / "filesystem.py"
    module_test_path = TESTS_ROOT / "modules" / "tools" / "test_workspace_write_policy.py"
    adapter_test_path = TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_protected_config.py"
    module_symbols = {"BlockedPathResolver", "WorkspaceWriteProtection", "evaluate_workspace_write_protection"}
    adapter_symbols = {"evaluate_workspace_write_protection"}
    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8-sig"), filename=str(adapter_path))
    adapter_definitions = {
        node.name
        for node in adapter_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert canonical_path.is_file()
    assert _find_spec_or_none(canonical_module) is not None
    assert module_symbols <= _top_level_bound_names(canonical_path)
    assert module_symbols.isdisjoint(adapter_definitions)
    assert _imports_all_symbols_from_without_aliases(adapter_path, canonical_module, adapter_symbols)
    assert module_test_path.is_file()
    assert _find_forbidden_imports(module_test_path, "opensprite.app") == []
    assert not _imports_symbols_or_star_from(adapter_test_path, canonical_module, module_symbols)
    assert _find_imports_outside(canonical_path, ()) == []


def test_ripgrep_runtime_has_one_process_integration_owner_and_filesystem_adapter_uses_it():
    canonical_module = "opensprite.integrations.processes.ripgrep"
    canonical_path = PROCESS_INTEGRATION_ROOT / "ripgrep.py"
    adapter_path = APP_WORKSPACE_TOOLS_ROOT / "filesystem.py"
    integration_test_path = TESTS_ROOT / "integrations" / "processes" / "test_ripgrep.py"
    runtime_symbols = {"find_ripgrep", "run_ripgrep"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in runtime_symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        definitions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for symbol in runtime_symbols & definitions:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8-sig"), filename=str(adapter_path))
    adapter_modules = {
        imported_module
        for node in adapter_tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(adapter_path, node)
    }

    assert canonical_path.is_file()
    assert _find_spec_or_none(canonical_module) is not None
    assert owners == {
        "find_ripgrep": [Path("integrations/processes/ripgrep.py")],
        "run_ripgrep": [Path("integrations/processes/ripgrep.py")],
    }
    assert canonical_module in adapter_modules
    assert integration_test_path.is_file()
    assert _find_forbidden_imports(integration_test_path, "opensprite.app") == []
    assert _find_imports_outside(canonical_path, ("opensprite.integrations.processes",)) == []


def test_code_navigation_tool_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.workspace.code_navigation"
    legacy_module = "opensprite.tools.code_navigation"
    canonical_path = APP_WORKSPACE_TOOLS_ROOT / "code_navigation.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == "CodeNavigationTool" for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "code_navigation.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/workspace/code_navigation.py")]
    assert _top_level_bound_names(APP_WORKSPACE_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "CodeNavigationTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "workspace" / "test_code_navigation.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_code_navigation.py").exists()
    assert violations == []


def test_filesystem_tools_have_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.workspace.filesystem"
    legacy_module = "opensprite.tools.filesystem"
    canonical_path = APP_WORKSPACE_TOOLS_ROOT / "filesystem.py"
    symbols = {
        "ReadFileTool",
        "GlobFilesTool",
        "GrepFilesTool",
        "ApplyPatchTool",
        "WriteFileTool",
        "ListDirTool",
        "EditFileTool",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in symbols:
                owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))

    expected_owner = [Path("app/tools/workspace/filesystem.py")]
    canonical_tests = (
        TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_navigation.py",
        TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_patch.py",
        TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_protected_config.py",
        TESTS_ROOT / "app" / "tools" / "workspace" / "test_filesystem_protected_skills.py",
        TESTS_ROOT / "app" / "tools" / "test_required_args.py",
    )
    legacy_tests = (
        TESTS_ROOT / "tools" / "test_filesystem_navigation.py",
        TESTS_ROOT / "tools" / "test_filesystem_patch.py",
        TESTS_ROOT / "tools" / "test_filesystem_protected_config.py",
        TESTS_ROOT / "tools" / "test_filesystem_protected_skills.py",
        TESTS_ROOT / "tools" / "test_required_args.py",
    )

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "filesystem.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == {symbol: expected_owner for symbol in symbols}
    assert _top_level_bound_names(APP_WORKSPACE_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert all(module_path.is_file() for module_path in canonical_tests)
    assert all(not module_path.exists() for module_path in legacy_tests)
    assert violations == []


def test_workspace_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_WORKSPACE_TOOLS_ROOT,
        (
            "yaml",
            "opensprite.config",
            "opensprite.core",
            "opensprite.integrations",
            "opensprite.modules",
        ),
    )
    assert violations == [], f"workspace tool adapters have an invalid dependency: {violations}"


def test_read_skill_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.skills.read"
    legacy_module = "opensprite.tools.skill"
    canonical_path = APP_SKILLS_TOOLS_ROOT / "read.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "ReadSkillTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "skill.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/skills/read.py")]
    assert _top_level_bound_names(APP_SKILLS_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "ReadSkillTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "skills" / "test_read.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_skill.py").exists()
    assert violations == []


def test_configure_skill_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.skills.configure"
    legacy_module = "opensprite.tools.skill_config"
    canonical_path = APP_SKILLS_TOOLS_ROOT / "configure.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "ConfigureSkillTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "skill_config.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/skills/configure.py")]
    assert _top_level_bound_names(APP_SKILLS_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "ConfigureSkillTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "skills" / "test_configure.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_skill_config.py").exists()
    assert violations == []


def test_skill_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_SKILLS_TOOLS_ROOT,
        ("opensprite.core", "opensprite.integrations", "opensprite.modules"),
    )
    assert violations == [], f"skill tool adapters have an invalid dependency: {violations}"


def test_configure_subagent_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.subagents.configure"
    legacy_module = "opensprite.tools.subagent_config"
    canonical_path = APP_SUBAGENT_TOOLS_ROOT / "configure.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "ConfigureSubagentTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "subagent_config.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/subagents/configure.py")]
    assert _top_level_bound_names(APP_SUBAGENT_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "ConfigureSubagentTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "subagents" / "test_subagent_configure.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_subagent_config.py").exists()
    assert violations == []


def test_delegate_tools_have_one_app_owner_and_no_legacy_modules():
    cases = (
        (
            "DelegateTool",
            "opensprite.app.tools.subagents.delegate",
            "opensprite.tools.delegate",
            Path("app/tools/subagents/delegate.py"),
            Path("tools/delegate.py"),
        ),
        (
            "DelegateManyTool",
            "opensprite.app.tools.subagents.delegate_many",
            "opensprite.tools.delegate_many",
            Path("app/tools/subagents/delegate_many.py"),
            Path("tools/delegate_many.py"),
        ),
    )

    for symbol, canonical_module, legacy_module, canonical_relative_path, legacy_relative_path in cases:
        owners: list[Path] = []
        violations = [
            *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
            *_find_forbidden_imports(TESTS_ROOT, legacy_module),
        ]
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            if any(isinstance(node, ast.ClassDef) and node.name == symbol for node in tree.body):
                owners.append(module_path.relative_to(OPENSPRITE_ROOT))

        assert (OPENSPRITE_ROOT / canonical_relative_path).is_file()
        assert not (OPENSPRITE_ROOT / legacy_relative_path).exists()
        assert _find_spec_or_none(canonical_module) is not None
        assert _find_spec_or_none(legacy_module) is None
        assert owners == [canonical_relative_path]
        assert violations == []

    assert _top_level_bound_names(APP_SUBAGENT_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert not ({"DelegateTool", "DelegateManyTool"} & _top_level_bound_names(initializer))
    assert (TESTS_ROOT / "app" / "tools" / "subagents" / "test_delegate_many.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_delegate_many.py").exists()


def test_run_workflow_tool_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.subagents.workflow"
    legacy_module = "opensprite.tools.workflow"
    canonical_path = APP_SUBAGENT_TOOLS_ROOT / "workflow.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(isinstance(node, ast.ClassDef) and node.name == "RunWorkflowTool" for node in tree.body):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "workflow.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/subagents/workflow.py")]
    assert _top_level_bound_names(APP_SUBAGENT_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "RunWorkflowTool" not in _top_level_bound_names(initializer)
    assert violations == []


def test_subagent_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_SUBAGENT_TOOLS_ROOT,
        ("opensprite.core", "opensprite.integrations", "opensprite.modules"),
    )
    assert violations == [], f"subagent tool adapters have an invalid dependency: {violations}"


def test_web_search_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.web.search"
    legacy_module = "opensprite.tools.web_search"
    canonical_path = APP_WEB_TOOLS_ROOT / "search.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "WebSearchTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "web_search.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/web/search.py")]
    assert _top_level_bound_names(APP_WEB_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "WebSearchTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "web" / "test_web_search.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_web_search.py").exists()
    assert violations == []


def test_web_fetch_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.web.fetch"
    legacy_module = "opensprite.tools.web_fetch"
    fetcher_module = "opensprite.integrations.web.fetcher"
    canonical_path = APP_WEB_TOOLS_ROOT / "fetch.py"
    owners: list[Path] = []
    fetcher_owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name == "WebFetchTool":
                owners.append(module_path.relative_to(OPENSPRITE_ROOT))
            if node.name == "WebFetcher":
                fetcher_owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "web_fetch.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _find_spec_or_none(fetcher_module) is not None
    assert owners == [Path("app/tools/web/fetch.py")]
    assert fetcher_owners == [Path("integrations/web/fetcher.py")]
    assert _top_level_bound_names(APP_WEB_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert {"WebFetchTool", "WebFetcher"}.isdisjoint(_top_level_bound_names(initializer))
    assert (TESTS_ROOT / "app" / "tools" / "web" / "test_fetch.py").is_file()
    assert (TESTS_ROOT / "integrations" / "web" / "test_fetcher.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_web_fetch.py").exists()
    assert violations == []


def test_web_fetcher_integration_only_imports_external_dependencies():
    fetcher_path = INTEGRATIONS_ROOT / "web" / "fetcher.py"
    violations = _find_imports_outside(
        fetcher_path,
        ("html2text", "httpx", "trafilatura"),
    )

    assert violations == []


def test_web_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_WEB_TOOLS_ROOT,
        (
            "httpx",
            "opensprite.config",
            "opensprite.core",
            "opensprite.integrations",
            "opensprite.modules",
        ),
    )
    assert violations == [], f"web tool adapters have an invalid dependency: {violations}"


def test_browser_navigation_policy_is_stdlib_only():
    policy_path = MODULES_ROOT / "tools" / "browser_navigation.py"

    assert policy_path.is_file()
    assert "validate_navigation_url" in _top_level_bound_names(policy_path)
    assert _find_imports_outside(policy_path, ()) == []


def test_legacy_media_outbound_module_does_not_return():
    legacy_module = "opensprite.media.outbound"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "outbound.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_speech_provider_integration_has_one_canonical_owner():
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "OpenAICompatibleSpeechProvider"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("integrations/media/audio.py")]


def test_media_integrations_only_import_provider_sdks_and_core():
    violations = _find_imports_outside(
        MEDIA_INTEGRATION_ROOT,
        ("httpx", "openai", "opensprite.core", "opensprite.integrations.media"),
    )
    assert violations == [], f"media integrations must depend inward on core: {violations}"


def test_legacy_media_audio_module_and_reexport_do_not_return():
    legacy_module = "opensprite.media.audio"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "audio.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_video_provider_integration_has_one_canonical_owner():
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "OpenAICompatibleVideoProvider"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("integrations/media/video.py")]


def test_legacy_media_video_module_and_reexport_do_not_return():
    legacy_module = "opensprite.media.video"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "video.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_image_provider_integrations_have_one_canonical_owner():
    symbols = {
        "MiniMaxImageProvider",
        "OpenAICompatibleImageProvider",
        "create_image_analysis_provider",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in symbols:
                owners[node.name].append(relative_path)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in symbols:
                owners[node.name].append(relative_path)

    expected_path = Path("integrations/media/image.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_legacy_media_image_module_and_reexports_do_not_return():
    symbols = {
        "MiniMaxImageProvider",
        "OpenAICompatibleImageProvider",
        "create_image_analysis_provider",
    }
    legacy_module = "opensprite.media.image"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "image.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_media_composition_functions_have_one_app_owner():
    symbols = {"create_media_router", "reload_media_router"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in symbols:
                owners[node.name].append(relative_path)

    expected_path = Path("app/media.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_media_router_status_has_one_module_owner():
    owners = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "media_router_status"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("modules/media/router.py")]


def test_app_media_only_composes_config_modules_and_integrations():
    module_path = APP_ROOT / "media.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed = (
        "opensprite.config",
        "opensprite.integrations.media",
        "opensprite.modules.media",
    )
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            root_package = imported_module.partition(".")[0]
            if root_package in STDLIB_MODULES:
                continue
            if not any(
                imported_module == package or imported_module.startswith(f"{package}.")
                for package in allowed
            ):
                violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}:{imported_module}")

    assert violations == []


def test_app_agent_runtime_only_imports_agent_and_lower_layers():
    violations = _find_imports_outside(
        AGENT_ROOT,
        (
            "opensprite.app.agent",
            "opensprite.app.llm",
            "opensprite.config",
            "opensprite.core",
            "opensprite.integrations",
            "opensprite.modules",
        ),
    )
    assert violations == [], f"app agent runtime has an invalid dependency: {violations}"


def test_agent_does_not_import_concrete_tool_adapters():
    violations = _find_forbidden_imports(AGENT_ROOT, "opensprite.app.tools")
    assert violations == [], f"agent must not depend on concrete tool adapters: {violations}"


def test_legacy_media_factory_module_does_not_return():
    legacy_module = "opensprite.media.factory"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (MEDIA_ROOT / "factory.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_core_run_tracking_only_imports_core_or_stdlib():
    violations = _find_imports_outside(
        CORE_RUN_TRACKING_ROOT,
        ("opensprite.core.contracts", "opensprite.core.run_tracking"),
    )
    assert violations == [], f"core run tracking must not depend on outer packages: {violations}"


def test_core_package_initializers_do_not_reexport_symbols():
    violations: list[str] = []
    for module_path in sorted(CORE_ROOT.rglob("__init__.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if not (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert violations == [], f"core package initializers must contain only a docstring: {violations}"


def test_json_serialization_has_one_core_owner_and_no_legacy_utils_module():
    canonical_module = "opensprite.core.serialization"
    legacy_module = "opensprite.utils.json_safe"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (CORE_ROOT / "serialization.py").is_file()
    assert not (OPENSPRITE_ROOT / "utils" / "json_safe.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_text_change_helpers_have_one_core_owner_and_no_legacy_utils_module():
    canonical_module = "opensprite.core.text_changes"
    legacy_module = "opensprite.utils.text_changes"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (CORE_ROOT / "text_changes.py").is_file()
    assert not (OPENSPRITE_ROOT / "utils" / "text_changes.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_token_counting_has_one_context_module_owner_and_no_legacy_utils_module():
    canonical_module = "opensprite.modules.context.token_counting"
    legacy_module = "opensprite.utils.tokens"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (MODULES_ROOT / "context" / "token_counting.py").is_file()
    assert not (OPENSPRITE_ROOT / "utils" / "tokens.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_request_contracts_have_one_core_owner_and_no_legacy_llms_module():
    canonical_module = "opensprite.core.contracts.llm_requests"
    legacy_module = "opensprite.llms.request_modes"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (CORE_CONTRACTS_ROOT / "llm_requests.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "request_modes.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_tool_argument_adapter_has_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.tool_arguments"
    legacy_module = "opensprite.llms.tool_args"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "tool_arguments.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "tool_args.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_response_adapters_have_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.response_adapters"
    legacy_module = "opensprite.llms.response_utils"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "response_adapters.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "response_utils.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_request_logging_has_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.request_logging"
    legacy_module = "opensprite.llms.request_log_fields"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "request_logging.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "request_log_fields.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_request_adapters_have_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.request_adapters"
    legacy_module = "opensprite.llms.request_builder"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "request_adapters.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "request_builder.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_openai_compatible_client_has_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.openai_compatible"
    legacy_module = "opensprite.llms.openai_compatible"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "openai_compatible.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "openai_compatible.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_openai_streaming_has_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.openai.streaming"
    legacy_module = "opensprite.llms.openai.streaming"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "openai" / "streaming.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "openai" / "streaming.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_openai_chat_provider_has_one_integration_owner_and_no_legacy_module():
    canonical_module = "opensprite.integrations.llm.openai.chat"
    legacy_module = "opensprite.llms.openai.chat"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "openai" / "chat.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "openai" / "chat.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_openai_responses_provider_has_one_integration_owner_and_no_legacy_package():
    canonical_module = "opensprite.integrations.llm.openai.responses"
    legacy_module = "opensprite.llms.openai.responses"
    legacy_package = "opensprite.llms.openai"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "openai" / "responses.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "openai").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _find_spec_or_none(legacy_package) is None
    assert violations == []


def test_openrouter_provider_has_one_integration_owner_and_no_legacy_package():
    canonical_module = "opensprite.integrations.llm.openrouter.chat"
    legacy_module = "opensprite.llms.openrouter.chat"
    legacy_package = "opensprite.llms.openrouter"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "openrouter" / "chat.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "openrouter").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _find_spec_or_none(legacy_package) is None
    assert violations == []


def test_minimax_provider_has_one_integration_owner_and_no_legacy_package():
    canonical_module = "opensprite.integrations.llm.minimax.chat"
    legacy_module = "opensprite.llms.minimax.chat"
    legacy_package = "opensprite.llms.minimax"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_package),
        *_find_forbidden_imports(TESTS_ROOT, legacy_package),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "minimax" / "chat.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "minimax").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _find_spec_or_none(legacy_package) is None
    assert violations == []


def test_llm_provider_specs_have_one_module_owner_and_no_legacy_module():
    canonical_module = "opensprite.modules.llm.provider_specs"
    legacy_module = "opensprite.llms.provider_specs"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (MODULES_ROOT / "llm" / "provider_specs.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "provider_specs.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_provider_vocabulary_has_one_module_owner_and_no_config_modules():
    canonical_modules = (
        "opensprite.modules.llm.provider_api_modes",
        "opensprite.modules.llm.provider_auth_types",
    )
    legacy_modules = (
        "opensprite.config.provider_api_modes",
        "opensprite.config.provider_auth_types",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    assert (MODULES_ROOT / "llm" / "provider_api_modes.py").is_file()
    assert (MODULES_ROOT / "llm" / "provider_auth_types.py").is_file()
    assert not (CONFIG_ROOT / "provider_api_modes.py").exists()
    assert not (CONFIG_ROOT / "provider_auth_types.py").exists()
    assert all(_find_spec_or_none(module) is not None for module in canonical_modules)
    assert all(_find_spec_or_none(module) is None for module in legacy_modules)
    assert violations == []


def test_llm_provider_ids_and_profile_rules_have_one_module_owner():
    canonical_modules = (
        "opensprite.modules.llm.provider_ids",
        "opensprite.modules.llm.provider_profile_rules",
    )
    legacy_modules = (
        "opensprite.config.provider_ids",
        "opensprite.config.provider_profile_rules",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    assert (MODULES_ROOT / "llm" / "provider_ids.py").is_file()
    assert (MODULES_ROOT / "llm" / "provider_profile_rules.py").is_file()
    assert not (CONFIG_ROOT / "provider_ids.py").exists()
    assert not (CONFIG_ROOT / "provider_profile_rules.py").exists()
    assert all(_find_spec_or_none(module) is not None for module in canonical_modules)
    assert all(_find_spec_or_none(module) is None for module in legacy_modules)
    assert violations == []


def test_llm_presets_code_resource_and_tests_have_one_module_owner():
    symbols = {"LLMPresets", "ProviderPreset", "load_llm_presets"}
    canonical_module = "opensprite.modules.llm.llm_presets"
    legacy_module = "opensprite.config.llm_presets"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (MODULES_ROOT / "llm" / "llm_presets.py").is_file()
    assert (MODULES_ROOT / "llm" / "llm-presets.json").is_file()
    assert (TESTS_ROOT / "modules" / "llm" / "test_llm_presets.py").is_file()
    assert not (CONFIG_ROOT / "llm_presets.py").exists()
    assert not (CONFIG_ROOT / "llm-presets.json").exists()
    assert not (TESTS_ROOT / "config" / "test_llm_presets.py").exists()
    assert symbols.isdisjoint(_top_level_bound_names(CONFIG_ROOT / "__init__.py"))
    assert symbols.isdisjoint(_explicit_all_names(CONFIG_ROOT / "__init__.py"))
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_provider_shared_types_and_errors_have_one_module_owner():
    canonical_modules = (
        "opensprite.modules.llm.provider_discovery_types",
        "opensprite.modules.llm.provider_errors",
    )
    legacy_modules = (
        "opensprite.config.provider_discovery_types",
        "opensprite.config.provider_errors",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    assert (MODULES_ROOT / "llm" / "provider_discovery_types.py").is_file()
    assert (MODULES_ROOT / "llm" / "provider_errors.py").is_file()
    assert not (CONFIG_ROOT / "provider_discovery_types.py").exists()
    assert not (CONFIG_ROOT / "provider_errors.py").exists()
    assert all(_find_spec_or_none(module) is not None for module in canonical_modules)
    assert all(_find_spec_or_none(module) is None for module in legacy_modules)
    assert violations == []


def test_provider_credential_resolution_has_one_auth_integration_owner():
    canonical_module = "opensprite.integrations.auth.provider_credentials"
    legacy_module = "opensprite.config.provider_credentials"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "auth" / "provider_credentials.py").is_file()
    assert not (CONFIG_ROOT / "provider_credentials.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_provider_discovery_has_one_llm_integration_owner():
    canonical_module = "opensprite.integrations.llm.provider_discovery"
    legacy_module = "opensprite.config.provider_discovery"
    canonical_tests = TESTS_ROOT / "integrations" / "llm" / "test_provider_discovery.py"
    settings_service_tests = TESTS_ROOT / "app" / "settings" / "test_providers.py"
    direct_test_names = {
        "test_fetch_openai_compatible_models_probes_v1_fallback",
        "test_fetch_openai_compatible_models_accepts_models_endpoint",
        "test_fetch_codex_models_filters_and_sorts",
        "test_fetch_openrouter_image_models_filters_by_modality",
    }
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (INTEGRATIONS_ROOT / "llm" / "provider_discovery.py").is_file()
    assert not (CONFIG_ROOT / "provider_discovery.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert direct_test_names <= _top_level_bound_names(canonical_tests)
    assert not direct_test_names & _top_level_bound_names(settings_service_tests)
    assert violations == []


def test_provider_settings_has_one_application_owner():
    canonical_module = "opensprite.app.settings.providers"
    legacy_module = "opensprite.config.provider_settings"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (APP_ROOT / "settings" / "providers.py").is_file()
    assert not (CONFIG_ROOT / "provider_settings.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "app" / "settings" / "test_providers.py").is_file()
    assert not (TESTS_ROOT / "config" / "test_provider_settings.py").exists()
    assert violations == []


def test_provider_settings_listing_has_one_application_owner():
    canonical_module = "opensprite.app.settings.provider_listing"
    legacy_module = "opensprite.config.provider_listing"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (APP_ROOT / "settings" / "provider_listing.py").is_file()
    assert not (CONFIG_ROOT / "provider_listing.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_provider_choices_have_one_llm_module_owner():
    canonical_module = "opensprite.modules.llm.provider_choices"
    legacy_module = "opensprite.config.provider_choices"
    canonical_path = MODULES_ROOT / "llm" / "provider_choices.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert canonical_path.is_file()
    assert not (CONFIG_ROOT / "provider_choices.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert "get_selected_provider" not in _top_level_bound_names(canonical_path)
    assert violations == []


def test_provider_public_payloads_have_one_application_owner():
    canonical_module = "opensprite.app.settings.provider_public"
    legacy_module = "opensprite.config.provider_public"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (APP_ROOT / "settings" / "provider_public.py").is_file()
    assert not (CONFIG_ROOT / "provider_public.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_provider_settings_state_has_one_application_owner():
    canonical_module = "opensprite.app.settings.provider_state"
    legacy_module = "opensprite.config.provider_state"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (APP_ROOT / "settings" / "provider_state.py").is_file()
    assert not (CONFIG_ROOT / "provider_state.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_provider_settings_persistence_has_one_integration_owner():
    canonical_module = "opensprite.integrations.persistence.provider_settings"
    legacy_module = "opensprite.config.provider_persistence"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (PERSISTENCE_INTEGRATION_ROOT / "provider_settings.py").is_file()
    assert not (CONFIG_ROOT / "provider_persistence.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_media_settings_has_one_application_owner():
    service_module = "opensprite.app.settings.media"
    misplaced_provider_config_module = "opensprite.integrations.media.provider_config"
    legacy_modules = (
        "opensprite.config.media_settings",
        "opensprite.config.provider_media",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    assert (APP_ROOT / "settings" / "media.py").is_file()
    assert not (CONFIG_ROOT / "media_settings.py").exists()
    assert not (CONFIG_ROOT / "provider_media.py").exists()
    assert not (MEDIA_INTEGRATION_ROOT / "provider_config.py").exists()
    assert _find_spec_or_none(service_module) is not None
    assert _find_spec_or_none(misplaced_provider_config_module) is None
    assert all(_find_spec_or_none(module) is None for module in legacy_modules)
    assert (TESTS_ROOT / "app" / "settings" / "test_media.py").is_file()
    assert not (TESTS_ROOT / "config" / "test_media_settings.py").exists()
    assert violations == []


def test_llm_registry_facade_is_removed():
    legacy_module = "opensprite.llms.registry"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert not (OPENSPRITE_ROOT / "llms" / "registry.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_runtime_profile_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.llm.runtime_profile"
    legacy_module = "opensprite.llms.runtime_profile"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (OPENSPRITE_ROOT / "app" / "llm" / "runtime_profile.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "runtime_profile.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_runtime_auth_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.llm.runtime_auth"
    legacy_module = "opensprite.llms.runtime_auth"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (OPENSPRITE_ROOT / "app" / "llm" / "runtime_auth.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "runtime_auth.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_runtime_credentials_have_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.llm.runtime_credentials"
    legacy_module = "opensprite.llms.runtime_credentials"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (OPENSPRITE_ROOT / "app" / "llm" / "runtime_credentials.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "runtime_credentials.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_runtime_provider_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.llm.runtime_provider"
    legacy_module = "opensprite.llms.runtime_provider"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (OPENSPRITE_ROOT / "app" / "llm" / "runtime_provider.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms" / "runtime_provider.py").exists()
    assert (TESTS_ROOT / "app" / "llm" / "test_runtime_provider.py").is_file()
    assert not (TESTS_ROOT / "llms" / "test_runtime_provider.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_llm_provider_composition_lives_in_app_and_legacy_package_is_removed():
    canonical_modules = (
        "opensprite.app.llm.provider_builders",
        "opensprite.app.llm.provider_factory",
    )
    legacy_modules = (
        "opensprite.llms",
        "opensprite.llms.provider_builders",
        "opensprite.llms.provider_factory",
    )
    violations: list[str] = []
    for legacy_module in legacy_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_module))

    assert (OPENSPRITE_ROOT / "app" / "llm" / "provider_builders.py").is_file()
    assert (OPENSPRITE_ROOT / "app" / "llm" / "provider_factory.py").is_file()
    assert (TESTS_ROOT / "integrations" / "llm" / "test_provider_default_models.py").is_file()
    assert not (OPENSPRITE_ROOT / "llms").exists()
    assert not (TESTS_ROOT / "llms").exists()
    assert all(_find_spec_or_none(module) is not None for module in canonical_modules)
    assert all(_find_spec_or_none(module) is None for module in legacy_modules)
    assert violations == []


def test_subagent_task_id_contract_has_one_canonical_owner():
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Name) and target.id == "SUBAGENT_TASK_ID_PATTERN"
                for target in targets
            ):
                owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/contracts/subagents.py")]


def test_removed_root_subagent_contract_module_does_not_return():
    legacy_module = "opensprite.subagent_contracts"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "subagent_contracts.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_persistence_contracts_have_one_canonical_owner():
    symbols = {
        "StoredMessage",
        "StoredRun",
        "StoredRunEvent",
        "StoredRunPart",
        "StoredRunFileChange",
        "StoredRunTrace",
        "StoredBackgroundProcess",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("core/contracts/persistence.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_curator_turn_result_contract_has_one_canonical_owner():
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "CuratorTurnResult"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/contracts/documents.py")]


def test_removed_curator_contract_module_and_reexports_do_not_return():
    symbol = "CuratorTurnResult"
    legacy_module = "opensprite.documents.curator_contracts"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    canonical_module = "opensprite.core.contracts.documents"
    initializer = CORE_CONTRACTS_ROOT / "__init__.py"
    assert symbol not in _top_level_bound_names(initializer)
    assert not _imports_symbols_or_star_from(initializer, canonical_module, {symbol})

    assert not (OPENSPRITE_ROOT / "documents" / "curator_contracts.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_bus_event_contracts_have_one_canonical_owner():
    symbols = {"InboundMessage", "OutboundMessage", "RunEvent", "SessionStatusEvent"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("core/contracts/bus_events.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_bus_events_module_and_reexports_do_not_return():
    symbols = {"InboundMessage", "OutboundMessage", "RunEvent", "SessionStatusEvent"}
    legacy_module = "opensprite.bus.events"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            tree = ast.parse(
                module_path.read_text(encoding="utf-8-sig"),
                filename=str(module_path),
            )
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                imported_names = {alias.name for alias in node.names}
                if _resolved_import(module_path, node) == "opensprite.bus" and (
                    "*" in imported_names or symbols & imported_names
                ):
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (BUS_ROOT / "events.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_persistence_contracts_are_not_imported_from_legacy_facades():
    symbols = {
        "StoredMessage",
        "StoredRun",
        "StoredRunEvent",
        "StoredRunPart",
        "StoredRunFileChange",
        "StoredRunTrace",
        "StoredBackgroundProcess",
    }
    legacy_modules = {"opensprite", "opensprite.storage", "opensprite.storage.base"}
    violations: list[str] = []

    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(package_root.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                resolved_import = _resolved_import(module_path, node)
                imported_names = {alias.name for alias in node.names}
                if resolved_import in legacy_modules and (
                    "*" in imported_names or symbols & imported_names
                ):
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []


def test_persistence_contracts_are_not_reexported_from_package_initializers():
    symbols = {
        "StoredMessage",
        "StoredRun",
        "StoredRunEvent",
        "StoredRunPart",
        "StoredRunFileChange",
        "StoredRunTrace",
        "StoredBackgroundProcess",
    }
    violations = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py"))
        if symbols & _top_level_bound_names(module_path)
        or _imports_symbols_or_star_from(
            module_path,
            "opensprite.core.contracts.persistence",
            symbols,
        )
    ]
    assert violations == []


def test_persistence_reexport_guard_rejects_wildcard_import(tmp_path):
    module_path = tmp_path / "__init__.py"
    module_path.write_text(
        "from opensprite.core.contracts.persistence import *\n",
        encoding="utf-8",
    )

    assert _imports_symbols_or_star_from(
        module_path,
        "opensprite.core.contracts.persistence",
        {"StoredMessage"},
    )


def test_storage_port_has_one_canonical_owner():
    owners: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "StorageProvider"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("core/ports/storage.py")]


def test_removed_storage_base_and_facade_imports_do_not_return():
    assert not (STORAGE_ROOT / "base.py").exists()
    legacy_modules = {"opensprite", "opensprite.storage", "opensprite.storage.base"}
    violations: list[str] = []

    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(package_root.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                resolved_import = _resolved_import(module_path, node)
                imported_names = {alias.name for alias in node.names}
                if resolved_import in legacy_modules and (
                    "*" in imported_names or "StorageProvider" in imported_names
                ):
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []


def test_storage_port_is_not_reexported_from_package_initializers():
    violations = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py"))
        if "StorageProvider" in _top_level_bound_names(module_path)
        or _imports_symbols_or_star_from(
            module_path,
            "opensprite.core.ports.storage",
            {"StorageProvider"},
        )
    ]
    assert violations == []


def test_memory_storage_has_one_canonical_owner():
    expected_path = Path("integrations/persistence/memory.py")
    owners: list[Path] = []
    bindings: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        if any(
            isinstance(node, ast.ClassDef) and node.name == "MemoryStorage"
            for node in tree.body
        ):
            owners.append(relative_path)
        if "MemoryStorage" in _top_level_bound_names(module_path):
            bindings.append(relative_path)

    assert owners == [expected_path]
    assert bindings == [expected_path]


def test_removed_memory_storage_module_and_facade_imports_do_not_return():
    canonical_module = "opensprite.integrations.persistence.memory"
    legacy_modules = {
        "opensprite",
        "opensprite.storage",
        "opensprite.storage.memory",
    }
    violations: list[str] = []

    assert not (STORAGE_ROOT / "memory.py").exists()

    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(package_root.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(
                        alias.name == "opensprite.storage.memory"
                        or alias.name.startswith("opensprite.storage.memory.")
                        for alias in node.names
                    ):
                        violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")
                    continue
                if not isinstance(node, ast.ImportFrom):
                    continue

                resolved_import = _resolved_import(module_path, node)
                imported_names = {alias.name for alias in node.names}
                imports_memory_storage = "MemoryStorage" in imported_names
                imports_legacy_wildcard = (
                    "*" in imported_names and resolved_import in legacy_modules
                )
                imports_canonical_wildcard = (
                    "*" in imported_names and resolved_import == canonical_module
                )
                if (
                    imports_memory_storage and resolved_import != canonical_module
                ) or imports_legacy_wildcard or imports_canonical_wildcard:
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []


def test_sqlite_database_primitives_have_one_canonical_owner():
    symbols = {
        "SQLITE_SCHEMA_VERSION",
        "SCHEMA_SCRIPT",
        "open_sqlite_connection",
        "ensure_sqlite_schema",
        "ensure_chat_row",
        "insert_message_row",
        "find_message_id",
    }
    expected_path = Path("integrations/persistence/sqlite/database.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        bound_names = _top_level_bound_names(module_path)
        for symbol in symbols & bound_names:
            owners[symbol].append(relative_path)

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_sqlite_database_has_no_legacy_upgrade_hooks():
    module_path = INTEGRATIONS_ROOT / "persistence" / "sqlite" / "database.py"
    source = module_path.read_text(encoding="utf-8-sig")
    bound_names = _top_level_bound_names(module_path)

    assert {
        "create_schema",
        "ensure_schema_upgrades",
        "table_exists",
    }.isdisjoint(bound_names)
    assert "ALTER TABLE" not in source
    assert "PRAGMA table_info" not in source


def test_sqlite_database_is_a_leaf_integration_module():
    module_path = INTEGRATIONS_ROOT / "persistence" / "sqlite" / "database.py"
    allowed_packages = (
        "opensprite.core.contracts.persistence",
        "opensprite.core.serialization",
    )
    violations: list[str] = []
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}:{imported_module}")

    assert violations == []


def test_search_policies_and_sqlite_adapter_do_not_depend_on_legacy_storage():
    violations = [
        *_find_forbidden_imports(SEARCH_MODULE_ROOT, "opensprite.storage"),
        *_find_forbidden_imports(SQLITE_PERSISTENCE_ROOT, "opensprite.storage"),
    ]
    assert violations == [], f"search must use shared persistence infrastructure: {violations}"


def test_sqlite_storage_adapter_has_one_canonical_owner():
    expected_path = Path("integrations/persistence/sqlite/storage.py")
    owners: list[Path] = []
    bindings: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        if any(
            isinstance(node, ast.ClassDef) and node.name == "SQLiteStorage"
            for node in tree.body
        ):
            owners.append(relative_path)
        if "SQLiteStorage" in _top_level_bound_names(module_path):
            bindings.append(relative_path)

    assert owners == [expected_path]
    assert bindings == [expected_path]


def test_removed_sqlite_storage_module_and_facade_imports_do_not_return():
    canonical_module = "opensprite.integrations.persistence.sqlite.storage"
    legacy_modules = {
        "opensprite",
        "opensprite.storage",
        "opensprite.storage.sqlite",
    }
    violations: list[str] = []

    assert not (STORAGE_ROOT / "sqlite.py").exists()

    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(package_root.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(
                        alias.name == "opensprite.storage.sqlite"
                        or alias.name.startswith("opensprite.storage.sqlite.")
                        for alias in node.names
                    ):
                        violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")
                    continue
                if not isinstance(node, ast.ImportFrom):
                    continue

                resolved_import = _resolved_import(module_path, node)
                imported_names = {alias.name for alias in node.names}
                imports_sqlite_storage = "SQLiteStorage" in imported_names
                imports_legacy_wildcard = (
                    "*" in imported_names and resolved_import in legacy_modules
                )
                imports_canonical_wildcard = (
                    "*" in imported_names and resolved_import == canonical_module
                )
                if (
                    imports_sqlite_storage and resolved_import != canonical_module
                ) or imports_legacy_wildcard or imports_canonical_wildcard:
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []


def test_storage_composition_has_one_canonical_owner():
    expected_path = Path("app/storage.py")
    owners: list[Path] = []
    bindings: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "create_storage"
            for node in tree.body
        ):
            owners.append(relative_path)
        if "create_storage" in _top_level_bound_names(module_path):
            bindings.append(relative_path)

    assert owners == [expected_path]
    assert bindings == [Path("app/bootstrap.py"), expected_path]


def test_removed_storage_package_and_imports_do_not_return():
    violations = _find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.storage")
    legacy_sources = sorted(STORAGE_ROOT.rglob("*.py")) if STORAGE_ROOT.exists() else []

    assert legacy_sources == []
    assert violations == [], f"storage composition must live under app: {violations}"


def test_removed_storage_test_root_does_not_return():
    assert not (TESTS_ROOT / "storage").exists()
    assert (TESTS_ROOT / "integrations" / "persistence" / "sqlite" / "test_storage.py").is_file()


def test_app_storage_composition_only_depends_on_config_core_and_integrations():
    module_path = OPENSPRITE_ROOT / "app" / "storage.py"
    allowed_packages = (
        "opensprite.config",
        "opensprite.core.ports.storage",
        "opensprite.integrations.persistence",
    )
    violations: list[str] = []
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}:{imported_module}")

    assert violations == []


def test_scheduling_composition_has_one_canonical_owner():
    expected_path = Path("app/scheduling.py")
    owners: list[Path] = []
    bindings: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "create_cron_manager"
            for node in tree.body
        ):
            owners.append(relative_path)
        if "create_cron_manager" in _top_level_bound_names(module_path):
            bindings.append(relative_path)

    assert owners == [expected_path]
    assert bindings == [Path("app/bootstrap.py"), expected_path]


def test_cron_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.scheduling.cron"
    legacy_module = "opensprite.tools.cron"
    canonical_path = APP_SCHEDULING_TOOLS_ROOT / "cron.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "CronTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "cron.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("app/tools/scheduling/cron.py")]
    assert _top_level_bound_names(APP_SCHEDULING_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert "CronTool" not in _top_level_bound_names(initializer)
    assert (TESTS_ROOT / "app" / "tools" / "scheduling" / "test_cron.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_cron.py").exists()
    assert violations == []


def test_cron_tool_adapter_only_imports_config_and_modules():
    violations = _find_imports_outside(
        APP_SCHEDULING_TOOLS_ROOT,
        ("opensprite.config", "opensprite.modules"),
    )
    assert violations == [], f"cron tool adapter has an invalid dependency: {violations}"


def test_scheduling_feature_has_explicit_module_owners():
    module_files = {
        path.relative_to(OPENSPRITE_ROOT)
        for path in SCHEDULING_MODULE_ROOT.glob("*.py")
    }

    assert module_files == {
        Path("modules/scheduling/__init__.py"),
        Path("modules/scheduling/manager.py"),
        Path("modules/scheduling/presentation.py"),
        Path("modules/scheduling/service.py"),
        Path("modules/scheduling/settings.py"),
        Path("modules/scheduling/types.py"),
    }


def test_schedule_settings_service_has_one_canonical_owner_and_no_config_alias():
    symbols = {
        "ScheduleSettingsError",
        "ScheduleSettingsValidationError",
        "ScheduleSettingsNotFound",
        "COMMON_TIMEZONES",
        "ScheduleSettingsService",
    }
    expected_path = Path("modules/scheduling/settings.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        declared_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_module = "opensprite.config.schedule_settings"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert not (CONFIG_ROOT / "schedule_settings.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "modules" / "scheduling" / "test_settings.py").is_file()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert violations == []


def test_removed_cron_package_and_imports_do_not_return():
    legacy_root = OPENSPRITE_ROOT / "cron"
    violations = _find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.cron")

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if "opensprite.cron" in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not legacy_root.exists()
    assert importlib.util.find_spec("opensprite.cron") is None
    assert violations == []


def test_scheduling_module_dependencies_stay_inward():
    violations = _find_imports_outside(
        SCHEDULING_MODULE_ROOT,
        (
            "croniter",
            "loguru",
            "opensprite.config",
            "opensprite.modules.scheduling",
        ),
    )

    assert violations == []


def test_cron_manager_requires_an_injected_session_workspace_resolver():
    module_path = SCHEDULING_MODULE_ROOT / "manager.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    manager_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CronManager"
    )
    constructor = next(
        node
        for node in manager_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    keyword_defaults = {
        argument.arg: default
        for argument, default in zip(
            constructor.args.kwonlyargs,
            constructor.args.kw_defaults,
            strict=True,
        )
    }

    assert set(keyword_defaults) == {
        "workspace_root",
        "workspace_for_session",
        "on_job",
    }
    assert keyword_defaults["workspace_for_session"] is None

    workspace_argument = next(
        argument
        for argument in constructor.args.kwonlyargs
        if argument.arg == "workspace_for_session"
    )
    assert ast.unparse(workspace_argument.annotation) == "Callable[[str], Path]"

    resolver_assignment = next(
        node
        for node in constructor.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr == "_workspace_for_session"
            for target in node.targets
        )
    )
    assert isinstance(resolver_assignment.value, ast.Name)
    assert resolver_assignment.value.id == "workspace_for_session"


def test_modules_package_initializers_do_not_reexport_symbols():
    violations: list[str] = []
    for module_path in sorted(MODULES_ROOT.rglob("__init__.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if not (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert violations == [], f"modules package initializers must contain only a docstring: {violations}"


def test_tool_validation_has_one_module_owner_and_no_legacy_module():
    canonical_module = "opensprite.modules.tools.validation"
    legacy_module = "opensprite.tools.validation"
    canonical_path = TOOLS_MODULE_ROOT / "validation.py"
    symbols = {
        "NON_EMPTY_STRING_PATTERN",
        "ValidationIssue",
        "format_param_preview",
        "validate_tool_params",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }
    expected_path = Path("modules/tools/validation.py")

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "validation.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _top_level_bound_names(TOOLS_MODULE_ROOT / "__init__.py") == set()
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert all(
        name.partition(".")[0] in STDLIB_MODULES or name.startswith("opensprite.core.")
        for name in imported_modules
    )
    assert violations == []


def test_tool_base_has_one_module_owner_and_no_legacy_module_or_reexport():
    canonical_module = "opensprite.modules.tools.base"
    legacy_module = "opensprite.tools.base"
    canonical_path = TOOLS_MODULE_ROOT / "base.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "Tool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "base.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("modules/tools/base.py")]
    assert all(
        name.partition(".")[0] in STDLIB_MODULES
        or name.startswith("opensprite.core.")
        or name.startswith("opensprite.modules.tools.validation")
        for name in imported_modules
    )
    assert violations == []


def test_tool_registry_has_one_module_owner_and_no_legacy_module_or_reexport():
    canonical_module = "opensprite.modules.tools.registry"
    legacy_module = "opensprite.tools.registry"
    canonical_path = TOOLS_MODULE_ROOT / "registry.py"
    symbols = {"BeforeToolExecuteHook", "ToolRegistry"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }
    expected_path = Path("modules/tools/registry.py")

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "registry.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert all(
        name.partition(".")[0] in STDLIB_MODULES
        or name.startswith("opensprite.core.")
        or name.startswith("opensprite.modules.tools.base")
        for name in imported_modules
    )
    assert violations == []


def test_batch_tool_has_one_module_owner_and_no_legacy_module_or_reexport():
    canonical_module = "opensprite.modules.tools.batch"
    legacy_module = "opensprite.tools.batch"
    canonical_path = TOOLS_MODULE_ROOT / "batch.py"
    owners: list[Path] = []
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "BatchTool"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "batch.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == [Path("modules/tools/batch.py")]
    assert all(
        name.partition(".")[0] in STDLIB_MODULES
        or name.startswith("opensprite.core.")
        or name.startswith("opensprite.modules.tools.")
        for name in imported_modules
    )
    assert (TESTS_ROOT / "modules" / "tools" / "test_batch.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_batch.py").exists()
    assert violations == []


def test_verification_result_classifier_has_one_core_owner():
    canonical_path = CORE_CONTRACTS_ROOT / "verification.py"
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "classify_verification_result"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }

    assert canonical_path.is_file()
    assert owners == [Path("core/contracts/verification.py")]
    assert "classify_verification_result" not in _top_level_bound_names(
        APP_VERIFICATION_TOOLS_ROOT / "verify.py"
    )
    assert all(
        name.partition(".")[0] in STDLIB_MODULES
        or name.startswith("opensprite.core.contracts.tool_results")
        for name in imported_modules
    )
    assert (TESTS_ROOT / "core" / "contracts" / "test_verification.py").is_file()


def test_verify_tool_adapter_has_one_app_owner_and_no_legacy_module():
    canonical_module = "opensprite.app.tools.verification.verify"
    legacy_module = "opensprite.tools.verify"
    canonical_path = APP_VERIFICATION_TOOLS_ROOT / "verify.py"
    symbols = {"VerifyCommandResult", "VerifyTool"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "verify.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    expected_owner = [Path("app/tools/verification/verify.py")]
    assert owners == {symbol: expected_owner for symbol in symbols}
    assert _top_level_bound_names(APP_VERIFICATION_TOOLS_ROOT / "__init__.py") == set()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert (TESTS_ROOT / "app" / "tools" / "verification" / "test_verify.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_verify.py").exists()
    assert violations == []


def test_verification_tool_adapters_only_import_allowed_lower_layers():
    violations = _find_imports_outside(
        APP_VERIFICATION_TOOLS_ROOT,
        ("opensprite.core", "opensprite.integrations", "opensprite.modules"),
    )
    assert violations == [], f"verification tool adapters have an invalid dependency: {violations}"


def test_process_runtime_policy_has_one_module_owner_and_no_legacy_module():
    canonical_module = "opensprite.modules.processes.runtime_policy"
    legacy_module = "opensprite.tools.process_runtime_policy"
    canonical_path = PROCESSES_MODULE_ROOT / "runtime_policy.py"
    symbols = {
        "PROCESS_LOST_ON_STARTUP_POLICY",
        "PROCESS_REATTACH_RUNTIME_LOCAL_REASON",
        "PROCESS_RECOVERY_RUNTIME_RESTART_REASON",
        "PROCESS_TERMINATION_CANCELLED",
        "PROCESS_TERMINATION_ERROR",
        "PROCESS_TERMINATION_EXIT",
        "PROCESS_TERMINATION_KILLED",
        "PROCESS_TERMINATION_RUNTIME_RESTART",
        "PROCESS_TERMINATION_SHUTDOWN",
        "PROCESS_TERMINATION_TIMEOUT",
        "PROCESS_TERMINATION_UNKNOWN",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            declared_names = {
                name for target in targets for name in _assigned_names(target)
            }
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }
    expected_path = Path("modules/processes/runtime_policy.py")

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "process_runtime_policy.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "modules" / "processes" / "test_runtime_policy.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_process_runtime_policy.py").exists()
    assert _top_level_bound_names(PROCESSES_MODULE_ROOT / "__init__.py") == set()
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert all(name.partition(".")[0] in STDLIB_MODULES for name in imported_modules)
    assert violations == []


def test_shell_runtime_has_one_process_integration_owner():
    canonical_module = "opensprite.integrations.processes.shell_runtime"
    canonical_launcher = "opensprite.integrations.processes._windows_shell_launcher"
    legacy_module = "opensprite.tools.shell_runtime"
    legacy_launcher = "opensprite.tools._windows_shell_launcher"
    canonical_path = PROCESS_INTEGRATION_ROOT / "shell_runtime.py"
    launcher_path = PROCESS_INTEGRATION_ROOT / "_windows_shell_launcher.py"
    symbols = {
        "CapturedOutputChunk",
        "drain_process_output",
        "format_captured_output",
        "start_exec_process",
        "start_shell_process",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations: list[str] = []
    for legacy_name in (legacy_module, legacy_launcher):
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_name))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_name))

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    shell_imports = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }
    launcher_imports = {
        imported_module
        for node in ast.walk(
            ast.parse(launcher_path.read_text(encoding="utf-8-sig"), filename=str(launcher_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(launcher_path, node)
    }
    expected_path = Path("integrations/processes/shell_runtime.py")

    assert canonical_path.is_file()
    assert launcher_path.is_file()
    assert not (TOOLS_ROOT / "shell_runtime.py").exists()
    assert not (TOOLS_ROOT / "_windows_shell_launcher.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(canonical_launcher) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert _find_spec_or_none(legacy_launcher) is None
    assert (TESTS_ROOT / "integrations" / "processes" / "test_shell_runtime.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_shell_runtime.py").exists()
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert all(
        name.partition(".")[0] in STDLIB_MODULES
        or name.startswith("opensprite.integrations.processes.")
        for name in shell_imports
    )
    assert all(name.partition(".")[0] in STDLIB_MODULES for name in launcher_imports)
    assert violations == []


def test_background_process_runtime_has_one_process_integration_owner():
    canonical_module = "opensprite.integrations.processes.background_runtime"
    legacy_module = "opensprite.tools.process_runtime"
    canonical_path = PROCESS_INTEGRATION_ROOT / "background_runtime.py"
    symbols = {"BackgroundProcessManager", "BackgroundSession", "SessionExitNotifier"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("integrations/processes/background_runtime.py")

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "process_runtime.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert violations == []


def test_user_overlay_identity_policy_has_one_canonical_owner():
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "resolve_user_overlay_id"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("modules/documents/identity.py")]


def test_user_overlay_identity_policy_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "identity.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_user_overlay_identity_module_does_not_return():
    legacy_module = "opensprite.documents.user_overlay_identity"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "user_overlay_identity.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_identity.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_curator_scope_policy_symbols_have_one_canonical_owner():
    symbols = {
        "CURATOR_MAINTENANCE_JOB_KEYS",
        "CURATOR_SCOPE_CHOICES",
        "_ordered_maintenance_job_keys",
        "resolve_curator_scope",
    }
    expected_path = Path("modules/documents/scope.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_curator_scope_policy_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "scope.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_curator_scope_module_does_not_return():
    legacy_module = "opensprite.documents.curator_scope"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "curator_scope.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_scope.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_curator_job_symbols_have_one_canonical_owner():
    symbols = {
        "SnapshotReader",
        "SessionRunner",
        "CuratorRequest",
        "CuratorJob",
        "CuratorMaintenanceServices",
    }
    expected_path = Path("modules/documents/jobs.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_curator_jobs_only_depend_on_core_contracts():
    module_path = DOCUMENTS_MODULE_ROOT / "jobs.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if imported_module == "opensprite.core.contracts.documents" or imported_module.startswith(
                "opensprite.core.contracts.documents."
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_curator_jobs_module_does_not_return():
    legacy_module = "opensprite.documents.curator_jobs"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "curator_jobs.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_jobs.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_coalescing_scheduler_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "CoalescingTaskScheduler" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/documents/scheduler.py")]


def test_coalescing_scheduler_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "scheduler.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_coalescing_scheduler_module_does_not_return():
    legacy_module = "opensprite.documents.coalescing_scheduler"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "coalescing_scheduler.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_scheduler.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_curator_shared_prompt_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "curator_shared_rules" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/documents/prompts.py")]


def test_curator_shared_prompt_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "prompts.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_curator_prompts_module_does_not_return():
    legacy_module = "opensprite.documents.curator_prompts"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "curator_prompts.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_prompts.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_skill_review_prompt_symbols_have_one_canonical_owner():
    symbols = {
        "SKILL_REVIEW_TRANSCRIPT_TOO_SHORT_REASON",
        "SKILL_REVIEW_SYSTEM",
        "format_stored_messages_for_transcript",
        "build_skill_review_user_content",
    }
    expected_path = Path("modules/documents/skill_review_prompts.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_skill_review_prompts_only_depend_on_core_contracts_and_document_policy():
    module_path = DOCUMENTS_MODULE_ROOT / "skill_review_prompts.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.core.contracts.tool_names",
        "opensprite.modules.documents.prompts",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_skill_review_prompts_module_does_not_return():
    legacy_module = "opensprite.documents.skill_review_prompts"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "skill_review_prompts.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_skill_review_prompts.py").is_file()
    assert not (TESTS_ROOT / "agent" / "test_skill_review_policy.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_skill_review_service_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "SkillReviewService" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/documents/skill_review.py")]
    assert (TESTS_ROOT / "modules" / "documents" / "test_skill_review_service.py").is_file()


def test_skill_review_service_does_not_import_outer_runtime_packages():
    module_path = DOCUMENTS_MODULE_ROOT / "skill_review.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    forbidden_packages = (
        "opensprite.app.agent",
        "opensprite.documents",
        "opensprite.integrations",
        "opensprite.tools",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if any(
                imported_module == forbidden or imported_module.startswith(f"{forbidden}.")
                for forbidden in forbidden_packages
            ):
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_durable_memory_safety_symbols_have_one_canonical_owner():
    symbols = {
        "DurableMemorySafetyError",
        "scan_durable_memory_text",
        "validate_durable_memory_text",
    }
    expected_path = Path("modules/documents/safety.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_durable_memory_safety_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "safety.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_safety_module_does_not_return():
    legacy_module = "opensprite.documents.safety"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "safety.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_safety.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_curator_state_policy_symbols_have_one_canonical_owner():
    symbols = {
        "CURATOR_STATE_SCHEMA_VERSION",
        "CURATOR_HISTORY_LIMIT",
        "default_curator_state",
        "safe_int",
        "string_list",
        "dict_list",
        "normalize_curator_state",
    }
    expected_path = Path("modules/documents/curator_state.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_curator_state_policy_only_imports_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "curator_state.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_curator_state_store_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "CuratorStateStore" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/documents/curator_state.py")]


def test_curator_state_store_only_depends_on_policy_logging_and_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "curator_state.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.modules.documents.curator_state",
        "opensprite.core.logging",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_curator_orchestrator_does_not_import_integrations():
    module_path = DOCUMENTS_MODULE_ROOT / "curator.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module == "opensprite.integrations" or imported_module.startswith(
                "opensprite.integrations."
            ):
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_curator_orchestrator_does_not_import_tools():
    module_path = DOCUMENTS_MODULE_ROOT / "curator.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module == "opensprite.tools" or imported_module.startswith("opensprite.tools."):
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_curator_orchestrator_stays_inside_document_module_boundaries():
    module_path = DOCUMENTS_MODULE_ROOT / "curator.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    forbidden_packages = (
        "opensprite.app.agent",
        "opensprite.documents",
        "opensprite.integrations",
        "opensprite.tools",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if any(
                imported_module == forbidden_package
                or imported_module.startswith(f"{forbidden_package}.")
                for forbidden_package in forbidden_packages
            ):
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_curator_service_has_one_canonical_owner():
    symbol = "CuratorService"
    canonical_module = DOCUMENTS_MODULE_ROOT / "curator.py"
    owners = [
        module_path.relative_to(PROJECT_ROOT).as_posix()
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if symbol in _top_level_bound_names(module_path)
    ]

    assert owners == [canonical_module.relative_to(PROJECT_ROOT).as_posix()]
    assert not (DOCUMENTS_ROOT / "curator.py").exists()
    assert not (TESTS_ROOT / "agent" / "test_curator.py").exists()
    assert not (TESTS_ROOT / "agent" / "test_curator_policy.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_curator_service.py").is_file()
    assert (TESTS_ROOT / "modules" / "documents" / "test_curator_runtime.py").is_file()
    assert _find_spec_or_none("opensprite.documents.curator") is None


def test_removed_document_curator_state_module_does_not_return():
    legacy_module = "opensprite.documents.curator_state"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "curator_state.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_curator_state.py").is_file()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_curator_state_store.py").is_file()
    assert not (TESTS_ROOT / "agent" / "test_curator_state.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_document_fingerprint_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "fingerprint_text_directory" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/documents/fingerprints.py")]


def test_document_fingerprint_only_imports_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "fingerprints.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_fingerprint_module_does_not_return():
    legacy_module = "opensprite.documents.document_fingerprints"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "document_fingerprints.py").exists()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_fingerprints.py").is_file()
    assert not (TESTS_ROOT / "documents" / "test_document_fingerprints.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_removed_document_base_abstractions_do_not_return():
    legacy_module = "opensprite.documents.base"
    removed_symbols = {
        "ConversationDocumentStore",
        "IncrementalStateStore",
        "ConversationConsolidator",
    }
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            source = module_path.read_text(encoding="utf-8-sig")
            if legacy_module in source:
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    remaining_owners: dict[str, list[Path]] = {symbol: [] for symbol in removed_symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in removed_symbols & declared_names:
            remaining_owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert not (OPENSPRITE_ROOT / "documents" / "base.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert remaining_owners == {symbol: [] for symbol in removed_symbols}
    assert violations == []


def test_managed_markdown_document_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "ManagedMarkdownDocument" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/documents/managed_markdown.py")]


def test_managed_markdown_document_only_imports_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "managed_markdown.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_managed_module_does_not_return():
    legacy_module = "opensprite.documents.managed"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "documents" / "managed.py").exists()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_managed_markdown.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_json_progress_store_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "JsonProgressStore" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/documents/progress_state.py")]


def test_json_progress_store_only_imports_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "progress_state.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_document_progress_state_module_and_dead_overlay_store_do_not_return():
    legacy_module = "opensprite.documents.state"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    overlay_state_owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "UserOverlayStateStore" in _top_level_bound_names(module_path)
    ]
    removed_path_symbols = {
        "USER_OVERLAY_STATE_FILENAME",
        "get_user_overlay_state_file",
    }
    remaining_path_owners: dict[str, list[Path]] = {symbol: [] for symbol in removed_path_symbols}
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in removed_path_symbols & declared_names:
            remaining_path_owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert not (OPENSPRITE_ROOT / "documents" / "state.py").exists()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_progress_state.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert overlay_state_owners == []
    assert remaining_path_owners == {symbol: [] for symbol in removed_path_symbols}
    assert violations == []


def test_memory_store_has_one_canonical_owner_and_no_legacy_class_name():
    store_owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "MemoryStore" in _top_level_bound_names(module_path)
    ]
    legacy_owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "MemoryDocumentStore" in _top_level_bound_names(module_path)
    ]

    assert store_owners == [Path("integrations/documents/memory.py")]
    assert legacy_owners == []


def test_memory_store_only_depends_on_paths_safety_and_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "memory.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.integrations.workspace.paths",
        "opensprite.modules.documents.safety",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_memory_store_is_not_exported_from_legacy_documents():
    legacy_module = "opensprite.documents.memory"
    symbols = {"MemoryDocumentStore", "MemoryStore"}
    violations: list[str] = []

    for symbol in symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )

    assert not (DOCUMENTS_ROOT / "memory.py").exists()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_memory_store.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_memory_tool.py").exists()
    assert (
        TESTS_ROOT / "app" / "tools" / "documents" / "test_memory_tool.py"
    ).is_file()
    assert violations == []


def test_user_overlay_store_symbols_have_one_canonical_owner():
    symbols = {"USER_OVERLAY_TEMPLATE", "UserOverlayStore", "UserOverlayIndexStore"}
    expected_path = Path("integrations/documents/user_overlay.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_user_overlay_stores_only_depend_on_paths_safety_and_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "user_overlay.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.integrations.workspace.paths",
        "opensprite.modules.documents.safety",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_user_overlay_stores_are_not_exported_from_legacy_documents():
    legacy_module = "opensprite.documents.user_overlay"
    symbols = {"USER_OVERLAY_TEMPLATE", "UserOverlayStore", "UserOverlayIndexStore"}
    violations: list[str] = []

    for symbol in symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )

    assert not (DOCUMENTS_ROOT / "user_overlay.py").exists()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_user_overlay_store.py").is_file()
    assert violations == []


def test_user_overlay_policy_symbols_have_one_canonical_owner():
    symbols = {
        "RelevantUserOverlayContextService",
        "UserOverlayPromotionService",
        "UserOverlayRetrievalPlanner",
    }
    expected_path = Path("modules/documents/user_overlay.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.modules.documents.user_overlay"
    legacy_context_module = CONTEXT_ROOT / "message_history.py"
    assert not legacy_context_module.exists()

    file_builder = CONTEXT_INTEGRATION_ROOT / "file_builder.py"
    file_builder_tree = ast.parse(
        file_builder.read_text(encoding="utf-8-sig"),
        filename=str(file_builder),
    )
    service_imports = [
        (alias.name, alias.asname)
        for node in file_builder_tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(file_builder, node) == canonical_module
        for alias in node.names
        if alias.name == "RelevantUserOverlayContextService"
    ]
    assert service_imports == [
        ("RelevantUserOverlayContextService", "_RelevantUserOverlayContextService")
    ]


def test_user_overlay_policy_only_depends_on_standard_library():
    module_path = DOCUMENTS_MODULE_ROOT / "user_overlay.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_user_overlay_policy_module_and_legacy_exports_do_not_return():
    legacy_module = "opensprite.documents.user_overlay"
    legacy_facade_symbols = {
        "RelevantUserOverlayContextService",
        "UserOverlayPromotionService",
        "UserOverlayRetrievalPlanner",
        "user_overlay",
    }
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for symbol in legacy_facade_symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (DOCUMENTS_ROOT / "user_overlay.py").exists()
    assert not (TESTS_ROOT / "documents" / "test_user_overlay.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_user_overlay.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert sorted(set(violations)) == []


def test_memory_consolidation_policy_has_one_canonical_owner():
    expected_path = Path("modules/documents/memory.py")
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "consolidate_memory" in _top_level_bound_names(module_path)
    ]

    assert owners == [expected_path]


def test_memory_consolidation_policy_only_depends_on_config_context_logging_and_document_policy():
    module_path = DOCUMENTS_MODULE_ROOT / "memory.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.config.schema",
        "opensprite.modules.context.token_counting",
        "opensprite.modules.documents.prompts",
        "opensprite.core.logging",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_memory_consolidation_service_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "MemoryConsolidationService" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("modules/documents/memory_consolidation.py")]
    assert not (TESTS_ROOT / "agent" / "test_consolidation.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_memory_consolidation.py").is_file()


def test_memory_consolidation_service_does_not_import_outer_runtime_packages():
    module_path = DOCUMENTS_MODULE_ROOT / "memory_consolidation.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    forbidden_packages = (
        "opensprite.app.agent",
        "opensprite.documents",
        "opensprite.integrations",
        "opensprite.tools",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if any(
                imported_module == forbidden or imported_module.startswith(f"{forbidden}.")
                for forbidden in forbidden_packages
            ):
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_memory_policy_module_and_legacy_exports_do_not_return():
    legacy_module = "opensprite.documents.memory"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for symbol in MEMORY_LEGACY_FACADE_SYMBOLS:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (DOCUMENTS_ROOT / "memory.py").exists()
    assert not (TESTS_ROOT / "documents" / "test_memory.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_memory.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert sorted(set(violations)) == []


def test_memory_legacy_facade_guard_detects_module_reexport(tmp_path):
    initializer = tmp_path / "__init__.py"
    initializer.write_text(
        "from opensprite.modules.documents import memory\n",
        encoding="utf-8",
    )

    assert MEMORY_LEGACY_FACADE_SYMBOLS & _top_level_bound_names(initializer) == {"memory"}


def test_user_profile_policy_symbols_have_one_canonical_owner():
    symbols = {
        "UserProfileConsolidator",
        "UserProfileUpdateService",
        "consolidate_user_profile",
    }
    expected_path = Path("modules/documents/user_profile.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert (TESTS_ROOT / "modules" / "documents" / "test_user_profile_update.py").is_file()


def test_user_profile_policy_only_depends_on_config_core_utils_and_document_policy():
    module_path = DOCUMENTS_MODULE_ROOT / "user_profile.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.config.schema",
        "opensprite.core.contracts.persistence",
        "opensprite.core.ports.storage",
        "opensprite.modules.documents.prompts",
        "opensprite.core.logging",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_user_profile_adapter_symbols_have_one_canonical_owner():
    symbols = {
        "RESPONSE_LANGUAGE_HEADER",
        "RL_START_MARKER",
        "RL_END_MARKER",
        "DEFAULT_RESPONSE_LANGUAGE_CONTENT",
        "RESPONSE_LANGUAGE_INTRO",
        "AUTO_PROFILE_HEADER",
        "START_MARKER",
        "END_MARKER",
        "DEFAULT_MANAGED_CONTENT",
        "AUTO_PROFILE_INTRO",
        "UserProfileStore",
        "load_user_profile_bootstrap_text",
        "create_user_profile_store",
    }
    expected_path = Path("integrations/documents/user_profile.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_user_profile_adapter_only_depends_on_paths_document_helpers_and_safety():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "user_profile.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.integrations.workspace.paths",
        "opensprite.integrations.documents.managed_markdown",
        "opensprite.integrations.documents.progress_state",
        "opensprite.modules.documents.safety",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_user_profile_module_and_legacy_exports_do_not_return():
    legacy_module = "opensprite.documents.user_profile"
    policy_symbols = {
        "UserProfileConsolidator",
        "UserProfileUpdateService",
        "consolidate_user_profile",
    }
    adapter_symbols = {
        "AUTO_PROFILE_HEADER",
        "DEFAULT_MANAGED_CONTENT",
        "END_MARKER",
        "START_MARKER",
        "UserProfileStore",
        "create_user_profile_store",
        "load_user_profile_bootstrap_text",
    }
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    for symbol in policy_symbols | {"UserProfileStore", "create_user_profile_store"}:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (DOCUMENTS_ROOT / "user_profile.py").exists()
    assert not (TESTS_ROOT / "documents" / "test_user_profile.py").exists()
    assert (TESTS_ROOT / "integrations" / "documents" / "test_user_profile.py").is_file()
    assert (TESTS_ROOT / "modules" / "documents" / "test_user_profile_policy.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert sorted(set(violations)) == []


def test_recent_summary_policy_symbols_have_one_canonical_owner():
    symbols = {
        "RecentSummaryConsolidator",
        "RecentSummaryUpdateService",
        "consolidate_recent_summary",
    }
    expected_path = Path("modules/documents/recent_summary.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        declared_names = _top_level_bound_names(module_path)
        for symbol in symbols & declared_names:
            owners[symbol].append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert (TESTS_ROOT / "modules" / "documents" / "test_recent_summary_update.py").is_file()


def test_recent_summary_policy_only_depends_on_config_core_context_logging_and_document_policy():
    module_path = DOCUMENTS_MODULE_ROOT / "recent_summary.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.config.schema",
        "opensprite.core.contracts.persistence",
        "opensprite.core.ports.storage",
        "opensprite.modules.context.token_counting",
        "opensprite.modules.documents.prompts",
        "opensprite.core.logging",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_removed_recent_summary_policy_module_and_exports_do_not_return():
    legacy_module = "opensprite.documents.recent_summary"
    symbols = {
        "RecentSummaryConsolidator",
        "RecentSummaryUpdateService",
        "consolidate_recent_summary",
    }
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for symbol in symbols:
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                OPENSPRITE_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )
        violations.extend(
            _find_forbidden_symbol_imports_or_access(
                TESTS_ROOT,
                ("opensprite.documents", legacy_module),
                symbol,
            )
        )

    assert not (DOCUMENTS_ROOT / "recent_summary.py").exists()
    assert (TESTS_ROOT / "modules" / "documents" / "test_recent_summary.py").is_file()
    assert not (TESTS_ROOT / "documents" / "test_recent_summary.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert sorted(set(violations)) == []


def test_recent_summary_store_has_one_canonical_owner():
    owners = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "RecentSummaryStore" in _top_level_bound_names(module_path)
    ]

    assert owners == [Path("integrations/documents/recent_summary.py")]


def test_recent_summary_store_only_depends_on_paths_progress_state_and_standard_library():
    module_path = DOCUMENTS_INTEGRATION_ROOT / "recent_summary.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    allowed_packages = (
        "opensprite.integrations.workspace.paths",
        "opensprite.integrations.documents.progress_state",
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_recent_summary_store_has_no_legacy_consumers():
    legacy_module = "opensprite.documents.recent_summary"
    symbol = "RecentSummaryStore"

    source_modules = ("opensprite.documents", legacy_module)
    violations = [
        *_find_forbidden_symbol_imports_or_access(OPENSPRITE_ROOT, source_modules, symbol),
        *_find_forbidden_symbol_imports_or_access(TESTS_ROOT, source_modules, symbol),
    ]

    assert (TESTS_ROOT / "integrations" / "documents" / "test_recent_summary_store.py").is_file()
    assert not (DOCUMENTS_ROOT / "recent_summary.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_forbidden_symbol_import_scanner_covers_legacy_import_shapes(tmp_path):
    cases = {
        "direct_submodule.py": "from opensprite.documents.recent_summary import RecentSummaryStore\n",
        "nested_submodule.py": (
            "def load():\n"
            "    from opensprite.documents.recent_summary import RecentSummaryStore\n"
        ),
        "package_facade.py": "from opensprite.documents import RecentSummaryStore\n",
        "aliased_submodule.py": (
            "import opensprite.documents.recent_summary as recent\n"
            "store = recent.RecentSummaryStore\n"
        ),
        "full_module.py": (
            "import opensprite.documents.recent_summary\n"
            "store = opensprite.documents.recent_summary.RecentSummaryStore\n"
        ),
        "imported_submodule.py": (
            "from opensprite.documents import recent_summary as recent\n"
            "store = recent.RecentSummaryStore\n"
        ),
        "aliased_package_submodule.py": (
            "import opensprite.documents as docs\n"
            "store = docs.recent_summary.RecentSummaryStore\n"
        ),
        "aliased_root_submodule.py": (
            "import opensprite as sprite\n"
            "store = sprite.documents.recent_summary.RecentSummaryStore\n"
        ),
        "assigned_package_alias.py": (
            "import opensprite.documents as docs\n"
            "legacy = docs\n"
            "store = legacy.RecentSummaryStore\n"
        ),
        "annotated_submodule_alias.py": (
            "import opensprite.documents as docs\n"
            "legacy: object = docs.recent_summary\n"
            "store = legacy.RecentSummaryStore\n"
        ),
        "reassigned_alias.py": (
            "import opensprite as sprite\n"
            "import opensprite.documents as docs\n"
            "legacy = sprite\n"
            "legacy = docs\n"
            "store = legacy.RecentSummaryStore\n"
        ),
        "self_reassigned_alias.py": (
            "import opensprite as sprite\n"
            "sprite = sprite.documents\n"
            "store = sprite.RecentSummaryStore\n"
        ),
        "bare_import_assigned_submodule_alias.py": (
            "import opensprite.documents\n"
            "legacy = opensprite.documents\n"
            "store = legacy.RecentSummaryStore\n"
        ),
        "canonical.py": (
            "from opensprite.integrations.documents.recent_summary import RecentSummaryStore\n"
        ),
    }
    for name, source in cases.items():
        (tmp_path / name).write_text(source, encoding="utf-8")

    violations = _find_forbidden_symbol_imports_or_access(
        tmp_path,
        ("opensprite.documents", "opensprite.documents.recent_summary"),
        "RecentSummaryStore",
    )

    assert len(violations) == 13
    assert all("canonical.py" not in violation for violation in violations)
    for name in set(cases) - {"canonical.py"}:
        assert any(name in violation for violation in violations)


def test_session_command_catalog_symbols_have_one_canonical_owner():
    symbols = {
        "CommandDef",
        "COMMAND_REGISTRY",
        "first_command_token",
        "normalize_command_name",
        "resolve_session_command",
        "render_command_usage",
        "iter_session_commands",
        "serialize_session_command",
        "session_command_catalog",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/session_commands/catalog.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_bus_session_commands_module_and_imports_do_not_return():
    symbols = {
        "CommandDef",
        "COMMAND_REGISTRY",
        "first_command_token",
        "normalize_command_name",
        "resolve_session_command",
        "render_command_usage",
        "iter_session_commands",
        "serialize_session_command",
        "session_command_catalog",
    }
    legacy_module = "opensprite.bus.session_commands"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (BUS_ROOT / "session_commands.py").exists()
    assert (TESTS_ROOT / "modules" / "session_commands" / "test_catalog.py").is_file()
    assert not (TESTS_ROOT / "bus" / "test_session_commands.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_session_command_catalog_is_a_dependency_leaf():
    violations = _find_imports_outside(
        SESSION_COMMANDS_MODULE_ROOT,
        ("opensprite.modules.session_commands",),
    )

    assert violations == []


def test_skill_loader_has_one_canonical_owner():
    symbols = {"Skill", "SkillsLoader"}
    expected_path = Path("modules/skills/loader.py")
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in symbols:
                owners[node.name].append(relative_path)

    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_skills_package_and_imports_do_not_return():
    legacy_root = OPENSPRITE_ROOT / "skills"
    violations = _find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.skills")

    assert not legacy_root.exists()
    assert importlib.util.find_spec("opensprite.skills") is None
    assert violations == []


def test_skill_loader_is_a_dependency_leaf():
    violations = _find_imports_outside(SKILLS_MODULE_ROOT, ("opensprite.modules.skills",))

    assert violations == []


def test_search_indexing_policy_has_one_canonical_owner():
    canonical_path = SEARCH_MODULE_ROOT / "indexing.py"
    legacy_path = SEARCH_ROOT / "indexing.py"
    violations = _find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.search.indexing")

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if "opensprite.search.indexing" in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert canonical_path.is_file()
    assert not legacy_path.exists()
    assert _find_spec_or_none("opensprite.search.indexing") is None
    assert violations == []


def test_search_feature_policies_only_depend_on_search_modules_and_core_contracts():
    violations = _find_imports_outside(
        SEARCH_MODULE_ROOT,
        (
            "opensprite.core.contracts.web_search",
            "opensprite.modules.search",
        ),
    )

    assert violations == []


def test_auth_adapters_are_owned_by_integrations():
    expected = {
        AUTH_INTEGRATION_ROOT / "codex.py",
        AUTH_INTEGRATION_ROOT / "copilot.py",
        AUTH_INTEGRATION_ROOT / "credentials.py",
    }
    legacy_root = OPENSPRITE_ROOT / "auth"

    assert all(path.is_file() for path in expected)
    assert not legacy_root.exists()
    assert importlib.util.find_spec("opensprite.auth") is None


def test_auth_legacy_import_path_does_not_return():
    forbidden = ("opensprite.auth",)
    violations: list[str] = []

    for legacy_path in forbidden:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, legacy_path))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, legacy_path))

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            content = module_path.read_text(encoding="utf-8-sig")
            for legacy_path in forbidden:
                if legacy_path in content:
                    violations.append(f"{module_path.relative_to(PROJECT_ROOT)}: {legacy_path}")

    assert violations == []


def test_integrations_package_initializers_do_not_reexport_symbols():
    violations: list[str] = []
    for module_path in sorted(INTEGRATIONS_ROOT.rglob("__init__.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if not (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert violations == [], f"integration package initializers must contain only a docstring: {violations}"


def test_network_environment_integration_has_one_canonical_owner():
    owners: list[Path] = []
    importers: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "apply_network_environment"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))
        if any(
            isinstance(node, ast.ImportFrom)
            and _resolved_import(module_path, node)
            == "opensprite.integrations.network.environment"
            and any(alias.name == "apply_network_environment" for alias in node.names)
            for node in ast.walk(tree)
        ):
            importers.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("integrations/network/environment.py")]
    assert importers == [
        Path("app/cli/commands_chat.py"),
        Path("app/runtime.py"),
        Path("integrations/web/settings/app_handlers.py"),
    ]


def test_removed_app_network_environment_module_and_imports_do_not_return():
    legacy_module = "opensprite.app.network_environment"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    app_initializer = OPENSPRITE_ROOT / "app" / "__init__.py"
    assert "apply_network_environment" not in _top_level_bound_names(app_initializer)
    assert not (OPENSPRITE_ROOT / "app" / "network_environment.py").exists()
    assert (TESTS_ROOT / "integrations" / "network" / "test_environment.py").is_file()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_network_environment_integration_has_explicit_dependencies():
    violations = _find_imports_outside(
        NETWORK_INTEGRATION_ROOT,
        (
            "opensprite.config",
            "opensprite.integrations.network",
            "opensprite.core.logging",
        ),
    )

    assert violations == []


def test_run_feature_modules_only_depend_on_inner_and_infrastructure_packages():
    violations = _find_imports_outside(
        RUN_MODULES_ROOT,
        (
            "opensprite.core",
            "opensprite.core.logging",
            "opensprite.modules.runs",
        ),
    )
    assert violations == [], f"run feature modules have an invalid outer dependency: {violations}"


def test_mcp_integration_only_depends_on_explicit_runtime_collaborators():
    violations = _find_imports_outside(
        MCP_INTEGRATION_ROOT,
        MCP_INTEGRATION_ALLOWED_IMPORTS,
    )
    assert violations == [], f"MCP integration has an invalid dependency: {violations}"


def test_process_integration_only_depends_on_explicit_runtime_collaborators():
    violations = _find_imports_outside(
        PROCESS_INTEGRATION_ROOT,
        PROCESS_INTEGRATION_ALLOWED_IMPORTS,
    )
    assert violations == [], f"process integration has an invalid dependency: {violations}"


def test_mcp_integration_dependency_guard_rejects_unrelated_tool_modules(tmp_path):
    module_path = tmp_path / "bad_integration.py"
    module_path.write_text(
        "from opensprite.tools.browser import BrowserNavigateTool\n",
        encoding="utf-8",
    )

    violations = _find_imports_outside(tmp_path, MCP_INTEGRATION_ALLOWED_IMPORTS)

    assert any("opensprite.tools.browser" in violation for violation in violations)


def test_removed_search_package_and_imports_do_not_return():
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.search"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.search"),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if "opensprite.search" in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not SEARCH_ROOT.exists()
    assert _find_spec_or_none("opensprite.search") is None
    assert violations == []


def test_search_composition_has_one_canonical_owner():
    owners: list[Path] = []
    importers: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "create_history_search_store"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))
        if any(
            isinstance(node, ast.ImportFrom)
            and _resolved_import(module_path, node) == "opensprite.app.search"
            and any(alias.name == "create_history_search_store" for alias in node.names)
            for node in ast.walk(tree)
        ):
            importers.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("app/search.py")]
    assert importers == [Path("app/bootstrap.py")]


def test_sqlite_search_adapter_has_one_canonical_owner():
    owners: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "SQLiteSearchStore"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    legacy_path = SEARCH_ROOT / "sqlite_store.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.search.sqlite_store"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.search.sqlite_store"),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if "opensprite.search.sqlite_store" in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert owners == [Path("integrations/persistence/sqlite/search.py")]
    assert not legacy_path.exists()
    assert _find_spec_or_none("opensprite.search.sqlite_store") is None
    assert violations == []


def test_search_contract_ownership_is_canonical():
    class_owners: dict[str, list[Path]] = {"SearchHit": [], "SearchStore": []}
    tool_name_owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in class_owners:
                class_owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and target.id == "HISTORY_SEARCH_TOOL_NAME" for target in targets):
                    tool_name_owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert class_owners == {
        "SearchHit": [Path("core/contracts/search.py")],
        "SearchStore": [Path("core/ports/search.py")],
    }
    assert tool_name_owners == [Path("core/contracts/tool_names.py")]


def test_tool_name_contracts_have_one_canonical_owner_and_no_reexports():
    symbols = {
        "BATCH_TOOL_NAME",
        "READ_FILE_TOOL_NAME",
        "LIST_DIR_TOOL_NAME",
        "GLOB_FILES_TOOL_NAME",
        "GREP_FILES_TOOL_NAME",
        "CODE_NAVIGATION_TOOL_NAME",
        "APPLY_PATCH_TOOL_NAME",
        "WRITE_FILE_TOOL_NAME",
        "EDIT_FILE_TOOL_NAME",
        "EXEC_TOOL_NAME",
        "PROCESS_TOOL_NAME",
        "READ_SKILL_TOOL_NAME",
        "CONFIGURE_SKILL_TOOL_NAME",
        "CONFIGURE_SUBAGENT_TOOL_NAME",
        "CONFIGURE_MCP_TOOL_NAME",
        "CREDENTIAL_STORE_TOOL_NAME",
        "CRON_TOOL_NAME",
        "HISTORY_SEARCH_TOOL_NAME",
        "DELEGATE_TOOL_NAME",
        "DELEGATE_MANY_TOOL_NAME",
        "RUN_WORKFLOW_TOOL_NAME",
        "WEB_SEARCH_TOOL_NAME",
        "WEB_FETCH_TOOL_NAME",
        "VERIFICATION_TOOL_NAME",
        "LIST_RUN_FILE_CHANGES_TOOL_NAME",
        "PREVIEW_RUN_FILE_CHANGE_REVERT_TOOL_NAME",
        "ANALYZE_IMAGE_TOOL_NAME",
        "OCR_IMAGE_TOOL_NAME",
        "TRANSCRIBE_AUDIO_TOOL_NAME",
        "ANALYZE_VIDEO_TOOL_NAME",
        "SEND_MEDIA_TOOL_NAME",
        "WORKSPACE_DISCOVERY_TOOL_NAMES",
        "WORKSPACE_WRITE_TOOL_NAMES",
        "EXECUTION_TOOL_NAMES",
        "RUN_TRACE_READ_TOOL_NAMES",
        "SKILL_REVIEW_TOOL_NAMES",
        "DELEGATED_EXECUTION_TOOL_NAMES",
        "MEDIA_ANALYSIS_TOOL_NAMES",
        "MEDIA_TOOL_NAMES",
        "WEB_SOURCE_TOOL_NAMES",
        "is_verification_tool_name",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("core/contracts/tool_names.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}

    canonical_module = "opensprite.core.contracts.tool_names"
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
        assert not _imports_symbols_or_star_from(initializer, canonical_module, symbols)


def test_removed_root_tool_names_module_does_not_return():
    legacy_module = "opensprite.tool_names"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if legacy_module in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not (OPENSPRITE_ROOT / "tool_names.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert violations == []


def test_removed_search_base_is_not_imported():
    assert not (SEARCH_ROOT / "base.py").exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.search.base"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.search.base"),
    ]
    assert violations == [], f"removed search.base must not be imported: {violations}"


def test_search_query_policy_only_imports_standard_library():
    module_path = SEARCH_MODULE_ROOT / "query_policy.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(module_path, node):
            if imported_module.partition(".")[0] not in STDLIB_MODULES:
                violations.append(f"{node.lineno}:{imported_module}")

    assert violations == []


def test_search_query_policy_symbols_have_one_canonical_owner():
    symbols = {
        "MAX_HISTORY_SEARCH_RESULTS",
        "MAX_HISTORY_SEARCH_QUERY_LENGTH",
        "MAX_HISTORY_SEARCH_QUERY_TOKENS",
        "_LITERAL_IDENTIFIER_TERM_PATTERN",
        "unicode_casefold",
        "bound_history_search_limit",
        "_literal_identifiers",
        "_query_without_literal_identifiers",
        "_deduplicated_query_tokens",
        "parse_history_search_terms",
        "_is_contiguous_script_character",
        "_unicode_search_spans",
        "_unicode_search_span_matches",
        "_matching_unicode_span_index",
        "find_history_search_token_offset",
        "validate_history_search_query",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/search/query_policy.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_search_query_policy_and_imports_do_not_return():
    legacy_path = SEARCH_ROOT / "query_policy.py"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.search.query_policy"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.search.query_policy"),
    ]

    for root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(root.rglob("*.py")):
            if module_path == Path(__file__):
                continue
            if "opensprite.search.query_policy" in module_path.read_text(encoding="utf-8-sig"):
                violations.append(str(module_path.relative_to(PROJECT_ROOT)))

    assert not legacy_path.exists()
    assert _find_spec_or_none("opensprite.search.query_policy") is None
    assert violations == []


def test_search_policy_is_not_reexported_from_sqlite_or_package_initializers():
    policy_symbols = {
        "MAX_HISTORY_SEARCH_RESULTS",
        "MAX_HISTORY_SEARCH_QUERY_LENGTH",
        "MAX_HISTORY_SEARCH_QUERY_TOKENS",
        "unicode_casefold",
        "bound_history_search_limit",
        "parse_history_search_terms",
        "find_history_search_token_offset",
        "validate_history_search_query",
    }
    sqlite_store_path = SQLITE_PERSISTENCE_ROOT / "search.py"
    assert policy_symbols.isdisjoint(_top_level_bound_names(sqlite_store_path))

    reexports = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py"))
        if policy_symbols & _top_level_bound_names(module_path)
    ]
    assert reexports == []

    legacy_imports: list[str] = []
    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        legacy_imports.extend(_find_search_query_policy_star_imports(package_root))
        for module_path in sorted(package_root.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                resolved_import = _resolved_import(module_path, node)
                imported_names = {alias.name for alias in node.names}
                leaked_names = sorted(policy_symbols & imported_names)
                if resolved_import == "opensprite.integrations.persistence.sqlite.search" and leaked_names:
                    legacy_imports.append(
                        f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}:{','.join(leaked_names)}"
                    )
    assert legacy_imports == []


def test_tools_do_not_import_sqlite_search_adapter():
    violations = _find_sqlite_search_adapter_dependencies(TOOLS_MODULE_ROOT)
    assert violations == [], f"tools module must depend on SearchStore and query policy, not SQLite: {violations}"


def test_sqlite_search_adapter_guard_detects_direct_and_reexported_imports(tmp_path):
    cases = {
        "direct.py": (
            "from opensprite.integrations.persistence.sqlite.search "
            "import SQLiteSearchStore\n"
        ),
        "package.py": (
            "from opensprite.integrations.persistence.sqlite import SQLiteSearchStore\n"
        ),
        "star.py": "from opensprite.integrations.persistence.sqlite import *\n",
        "attribute.py": (
            "import opensprite.integrations.persistence.sqlite as sqlite\n"
            "store = sqlite.SQLiteSearchStore\n"
        ),
    }
    for filename, source in cases.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")

    violations = _find_sqlite_search_adapter_dependencies(tmp_path)

    assert len(violations) == len(cases)


def test_search_query_policy_guard_detects_star_import(tmp_path):
    (tmp_path / "legacy.py").write_text(
        "from opensprite.modules.search.query_policy import *\n",
        encoding="utf-8",
    )

    violations = _find_search_query_policy_star_imports(tmp_path)

    assert len(violations) == 1


def test_removed_search_policy_helpers_are_not_reintroduced():
    removed_names = {"_unicode_casefold", "_bounded_limit", "_search_casefold"}
    declarations: list[str] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in removed_names:
                declarations.append(
                    f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}:{node.name}"
                )

    assert declarations == []


def test_message_contract_and_channel_port_ownership_is_canonical():
    class_owners: dict[str, list[Path]] = {
        "UserMessage": [],
        "AssistantMessage": [],
        "MessageAdapter": [],
    }
    constant_owners: dict[str, list[Path]] = {
        "CLIENT_TURN_ID_METADATA_KEY": [],
        "RESPONSE_KIND_METADATA_KEY": [],
        "SESSION_COMMAND_RESPONSE_KIND": [],
    }

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in class_owners:
                class_owners[node.name].append(relative_path)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in constant_owners:
                        constant_owners[target.id].append(relative_path)

    assert class_owners == {
        "UserMessage": [Path("core/contracts/messages.py")],
        "AssistantMessage": [Path("core/contracts/messages.py")],
        "MessageAdapter": [Path("core/ports/channels.py")],
    }
    assert constant_owners == {
        "CLIENT_TURN_ID_METADATA_KEY": [Path("core/contracts/messages.py")],
        "RESPONSE_KIND_METADATA_KEY": [Path("core/contracts/messages.py")],
        "SESSION_COMMAND_RESPONSE_KIND": [Path("core/contracts/messages.py")],
    }


def test_message_symbols_are_not_reexported_from_package_initializers():
    message_symbols = {
        "CLIENT_TURN_ID_METADATA_KEY",
        "RESPONSE_KIND_METADATA_KEY",
        "SESSION_COMMAND_RESPONSE_KIND",
        "UserMessage",
        "AssistantMessage",
        "MessageAdapter",
    }
    violations: list[str] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        bound_names: set[str] = set()
        exported_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                bound_names.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bound_names.add(target.id)
                        if target.id == "__all__":
                            exported_names.update(ast.literal_eval(node.value))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                bound_names.add(node.target.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound_names.add(node.name)

        leaked_symbols = sorted(message_symbols & (bound_names | exported_names))
        if leaked_symbols:
            violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{','.join(leaked_symbols)}")

    legacy_imports: list[str] = []
    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for symbol in message_symbols:
            legacy_imports.extend(_find_forbidden_imports(package_root, f"opensprite.{symbol}"))

    assert violations == [], f"message symbols must use canonical core modules: {violations}"
    assert legacy_imports == []


def test_removed_bus_message_is_not_imported():
    assert not (OPENSPRITE_ROOT / "bus" / "message.py").exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.bus.message"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.bus.message"),
    ]
    assert violations == [], f"removed bus.message must not be imported: {violations}"


def test_removed_runs_package_is_not_imported():
    assert not RUNS_ROOT.exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.runs"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.runs"),
    ]
    assert violations == [], f"removed opensprite.runs package must not be imported: {violations}"


def test_tool_selection_symbols_have_one_canonical_owner():
    symbols = {"ToolSelectionResolution", "ToolSelectionResolver"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))

    expected_path = Path("app/agent/tool_selection.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_tools_selection_is_not_imported_or_reexported():
    assert not (TOOLS_ROOT / "selection.py").exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.tools.selection"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.tools.selection"),
    ]
    assert violations == [], f"removed tools.selection must not be imported: {violations}"

    selection_symbols = {"ToolSelectionResolution", "ToolSelectionResolver"}
    reexports = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py"))
        if selection_symbols & _top_level_bound_names(module_path)
    ]
    assert reexports == [], "tool selection must be imported from its canonical module"


def test_tool_loop_guardrail_symbols_have_one_canonical_owner():
    symbols = {
        "IDEMPOTENT_TOOL_NAMES",
        "MUTATING_TOOL_NAMES",
        "ToolLoopGuardrailConfig",
        "ToolCallSignature",
        "ToolLoopGuardrailDecision",
        "ToolLoopGuardrail",
        "build_toolguard_synthetic_result",
        "append_toolguard_guidance",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("app/agent/execution_support/tool_loop_guardrail.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_tools_loop_guardrail_is_not_imported_or_reexported():
    assert not (TOOLS_ROOT / "loop_guardrail.py").exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.tools.loop_guardrail"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.tools.loop_guardrail"),
    ]
    assert violations == [], f"removed tools.loop_guardrail must not be imported: {violations}"

    guardrail_symbols = {
        "IDEMPOTENT_TOOL_NAMES",
        "MUTATING_TOOL_NAMES",
        "ToolLoopGuardrailConfig",
        "ToolCallSignature",
        "ToolLoopGuardrailDecision",
        "ToolLoopGuardrail",
        "build_toolguard_synthetic_result",
        "append_toolguard_guidance",
    }
    reexports = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py"))
        if guardrail_symbols & _top_level_bound_names(module_path)
    ]
    assert reexports == [], "tool loop guardrail must be imported from its canonical module"


def test_tool_registration_symbols_have_one_canonical_owner():
    symbols = {
        "BROWSER_TOOL_NAMES",
        "registered_browser_tool_names",
        "unregister_browser_tools",
        "reload_browser_tools",
        "register_memory_tool",
        "register_run_trace_tools",
        "register_filesystem_tools",
        "register_skill_tools",
        "register_shell_tools",
        "register_verify_tools",
        "register_config_tools",
        "register_web_tools",
        "reload_web_search_tools",
        "register_browser_tools",
        "register_media_tools",
        "register_delegate_tools",
        "register_workflow_tools",
        "register_history_search_tool",
        "register_cron_tools",
        "register_batch_tools",
        "register_default_tools",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("app/tools/registration.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_tools_registration_is_not_imported_or_reexported():
    removed_modules = (
        "opensprite.tools.registration",
        "opensprite.app.agent.tool_registration",
    )
    assert not (TOOLS_ROOT / "registration.py").exists()
    assert not (AGENT_ROOT / "tool_registration.py").exists()
    violations: list[str] = []
    for removed_module in removed_modules:
        violations.extend(_find_forbidden_imports(OPENSPRITE_ROOT, removed_module))
        violations.extend(_find_forbidden_imports(TESTS_ROOT, removed_module))
    assert all(_find_spec_or_none(module_name) is None for module_name in removed_modules)
    assert violations == [], f"removed tool registration modules must not be imported: {violations}"

    registration_symbols = {
        "BROWSER_TOOL_NAMES",
        "registered_browser_tool_names",
        "unregister_browser_tools",
        "reload_browser_tools",
        "register_memory_tool",
        "register_run_trace_tools",
        "register_filesystem_tools",
        "register_skill_tools",
        "register_shell_tools",
        "register_verify_tools",
        "register_config_tools",
        "register_web_tools",
        "reload_web_search_tools",
        "register_browser_tools",
        "register_media_tools",
        "register_delegate_tools",
        "register_workflow_tools",
        "register_history_search_tool",
        "register_cron_tools",
        "register_batch_tools",
        "register_default_tools",
    }
    reexports = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("__init__.py"))
        if registration_symbols & _top_level_bound_names(module_path)
    ]
    assert reexports == [], "tool registration must be imported from its canonical app module"


def test_tool_registration_tests_follow_app_ownership():
    expected_test = TESTS_ROOT / "app" / "tools" / "test_registration.py"
    assert expected_test.is_file()
    assert not (TESTS_ROOT / "agent" / "test_tool_registration.py").exists()
    violations = _find_forbidden_imports(
        TESTS_ROOT / "tools",
        "opensprite.app.tools.registration",
    )
    assert violations == [], f"tool adapter tests must not own app registration: {violations}"


def test_delegation_contract_has_one_agent_owner():
    symbols = {"StoredDelegatedTask", "selected_delegated_task"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("app/agent/delegation_contracts.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_delegation_contract_is_not_rebound_by_consumer_modules():
    symbols = {"StoredDelegatedTask", "selected_delegated_task"}
    canonical_path = AGENT_ROOT / "delegation_contracts.py"
    violations = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if module_path != canonical_path and symbols & _top_level_bound_names(module_path)
    ]
    assert violations == []


def test_storage_does_not_reexport_agent_delegation_contracts():
    symbols = {
        "StoredDelegatedTask",
        "coerce_stored_delegated_task",
        "coerce_stored_delegated_tasks",
        "selected_delegated_task",
    }
    legacy_bindings = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(STORAGE_ROOT.rglob("*.py"))
        if symbols & _top_level_bound_names(module_path)
    ]
    assert legacy_bindings == []


def test_delegation_contract_is_only_imported_by_agent_runtime():
    violations: list[str] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        if module_path.is_relative_to(AGENT_ROOT):
            continue
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            imported_modules = _imported_modules(module_path, node)
            if "opensprite.app.agent.delegation_contracts" in imported_modules:
                violations.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    assert violations == []


def test_run_tests_follow_production_ownership():
    expected_paths = {
        TESTS_ROOT / "agent" / "execution_support" / "test_run_hooks.py",
        TESTS_ROOT / "modules" / "runs" / "test_presentation.py",
        TESTS_ROOT / "modules" / "runs" / "test_trace_recorder.py",
    }
    assert all(path.is_file() for path in expected_paths)
    assert not (TESTS_ROOT / "agent" / "test_run_trace_services.py").exists()
    assert not (TESTS_ROOT / "agent" / "test_run_progress_notice_policy.py").exists()


def test_run_lifecycle_symbols_have_one_canonical_owner():
    symbols = {"PreparedTurnLifecycleInput", "ActiveTurnRun", "RunLifecycleService"}
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("modules/runs/turn_lifecycle.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_removed_agent_run_lifecycle_is_not_imported():
    module_name = "opensprite.app.agent.run_lifecycle"
    assert not (AGENT_ROOT / "run_lifecycle.py").exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, module_name),
        *_find_forbidden_imports(TESTS_ROOT, module_name),
    ]
    assert violations == [], f"removed agent run lifecycle must not be imported: {violations}"


def test_run_presentation_symbols_have_one_canonical_owner():
    symbols = {
        "MAX_SERIALIZED_RUN_EVENTS",
        "MAX_SERIALIZED_TEXT_EVENTS",
        "RUN_CANCELLED_STATUSES",
        "RUN_FAILED_STATUSES",
        "RUN_SCHEMA_VERSION",
        "RUN_STATUS_WARNING_STATUSES",
        "RUN_SUMMARY_STATUS_FAILED",
        "RUN_SUMMARY_STATUS_NOT_ATTEMPTED",
        "RUN_SUMMARY_STATUS_PASSED",
        "RUN_WARNING_EXTERNAL_HTTP_VIA_EXEC",
        "RUN_WARNING_PARALLEL_DELEGATION_CANCELLED",
        "RUN_WARNING_PARALLEL_DELEGATION_FAILED",
        "RUN_WARNING_TOOL_ERROR",
        "RUN_WARNING_VERIFICATION_NOT_PASSED",
        "compact_run_events",
        "event_artifact",
        "file_change_artifact",
        "run_event_envelope",
        "run_event_kind",
        "run_event_status",
        "run_part_artifact",
        "run_part_kind",
        "run_part_state",
        "serialize_diff_summary",
        "serialize_file_change",
        "serialize_run_artifacts",
        "serialize_run_event",
        "serialize_run_event_counts",
        "serialize_run_events",
        "serialize_run_part",
        "serialize_run_parts",
        "serialize_run_summary",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/runs/presentation.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_web_api_does_not_reexport_run_presentation_helpers():
    presentation_bindings = {
        "serialize_diff_summary",
        "serialize_file_change",
        "serialize_run_artifacts",
        "serialize_run_event_counts",
        "serialize_run_events",
        "serialize_run_part",
        "serialize_run_summary",
        "serialize_run_trace_entries",
        "serialize_session_entries",
    }
    web_api_bindings = _top_level_bound_names(INTEGRATIONS_ROOT / "web" / "api.py")
    assert presentation_bindings.isdisjoint(web_api_bindings)


def test_session_entry_symbols_have_one_canonical_owner():
    symbols = {
        "serialize_message_entry",
        "serialize_run_trace_entries",
        "serialize_session_entries",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in owners:
                owners[node.name].append(relative_path)

    expected_path = Path("modules/runs/session_entries.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_run_state_ownership_is_canonical():
    expected_symbols = {
        "ActiveRunState",
        "RunBusyError",
        "RunCancelledError",
        "AgentRunStateService",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in expected_symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in owners:
                owners[node.name].append(module_path.relative_to(OPENSPRITE_ROOT))

    expected_path = Path("core/run_tracking/state.py")
    assert owners == {symbol: [expected_path] for symbol in expected_symbols}


def test_top_level_binding_guard_detects_aliases_and_exports(tmp_path):
    module_path = tmp_path / "module.py"
    cases = (
        "from example import LegacySymbol\n",
        "from example import source\nLegacySymbol = source.LegacySymbol\n",
        "__all__ = ['LegacySymbol']\n",
        "from example import *\n",
    )

    for source in cases:
        module_path.write_text(source, encoding="utf-8")
        bound_names = _top_level_bound_names(module_path)
        assert "LegacySymbol" in bound_names or "*" in bound_names, source


def test_run_protocol_contracts_have_one_canonical_location():
    assert (CORE_CONTRACTS_ROOT / "run_events.py").is_file()
    assert (CORE_CONTRACTS_ROOT / "run_lifecycle.py").is_file()


def test_run_hook_symbols_have_one_canonical_owner():
    symbols = {
        "PROGRESS_NOTICE_TOOL_NAMES",
        "tool_warrants_progress_notice",
        "RunHookService",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("app/agent/execution_support/run_hooks.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_cli_does_not_depend_on_agent_runtime():
    violations = _find_forbidden_imports(APP_CLI_ROOT, "opensprite.app.agent")
    assert violations == [], f"CLI must not import agent runtime internals: {violations}"


def test_turn_source_contracts_are_not_reexported_from_agent():
    bound_names = _top_level_bound_names(AGENT_ROOT / "turn_input.py")
    assert {"TURN_SOURCE_METADATA_KEY", "CLI_VIA_WEB_TURN_SOURCE"}.isdisjoint(bound_names)


def test_run_file_change_service_has_one_canonical_owner():
    owners: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "RunFileChangeService"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("modules/runs/file_changes.py")]


def test_run_trace_recorder_symbols_have_one_canonical_owner():
    symbols = {
        "RUN_PART_CONTENT_MAX_CHARS",
        "TERMINAL_EVENT_DELIVERY_TIMEOUT_SECONDS",
        "TRACE_OPERATION_TYPE_FIELD",
        "TRACE_TARGET_FIELD",
        "TRACE_ROLLBACK_AVAILABLE_FIELD",
        "truncate_run_part_content",
        "RunEventPersistenceError",
        "RunEventSink",
        "RunTraceRecorder",
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    expected_path = Path("modules/runs/trace_recorder.py")
    assert owners == {symbol: [expected_path] for symbol in symbols}


def test_run_response_finalizer_has_one_canonical_owner():
    owners: list[Path] = []
    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "RunResponseFinalizer"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    assert owners == [Path("modules/runs/response_finalizer.py")]


def test_removed_agent_response_finalizer_is_not_imported():
    assert not (AGENT_ROOT / "response_finalizer.py").exists()
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, "opensprite.app.agent.response_finalizer"),
        *_find_forbidden_imports(TESTS_ROOT, "opensprite.app.agent.response_finalizer"),
    ]
    assert violations == [], f"removed agent.response_finalizer must not be imported: {violations}"

    legacy_bindings = [
        module_path.relative_to(OPENSPRITE_ROOT)
        for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py"))
        if "AgentResponseFinalizer" in _top_level_bound_names(module_path)
    ]
    assert legacy_bindings == [], f"removed AgentResponseFinalizer must not be rebound: {legacy_bindings}"


def test_background_session_notification_service_has_one_canonical_owner():
    canonical_path = PROCESS_INTEGRATION_ROOT / "background_session_notifications.py"
    legacy_module = "opensprite.app.agent.background_session_notifications"
    owners: list[Path] = []

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "BackgroundSessionNotificationService"
            for node in tree.body
        ):
            owners.append(module_path.relative_to(OPENSPRITE_ROOT))

    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert canonical_path.is_file()
    assert not (AGENT_ROOT / "background_session_notifications.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (
        TESTS_ROOT / "integrations" / "processes" / "test_background_session_notifications.py"
    ).is_file()
    assert not (TESTS_ROOT / "agent" / "test_background_session_notifications.py").exists()
    assert _top_level_bound_names(PROCESS_INTEGRATION_ROOT / "__init__.py") == set()
    assert owners == [Path("integrations/processes/background_session_notifications.py")]
    assert violations == []


def test_pytest_output_parser_has_one_canonical_owner_and_no_tools_alias():
    symbols = {"PYTEST_NO_TESTS_MARKERS", "pytest_collected_no_tests"}
    canonical_path = VERIFICATION_INTEGRATION_ROOT / "pytest_output.py"
    legacy_module = "opensprite.tools.verification_output_policy"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]
    owners: dict[str, list[Path]] = {symbol: [] for symbol in symbols}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in symbols & declared_names:
                owners[name].append(relative_path)

    imported_modules = {
        imported_module
        for node in ast.walk(
            ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
        )
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(canonical_path, node)
    }
    expected_path = Path("integrations/verification/pytest_output.py")

    assert canonical_path.is_file()
    assert not (TOOLS_ROOT / "verification_output_policy.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "integrations" / "verification" / "test_pytest_output.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_verification_output_policy.py").exists()
    assert _top_level_bound_names(VERIFICATION_INTEGRATION_ROOT / "__init__.py") == set()
    assert owners == {symbol: [expected_path] for symbol in symbols}
    assert all(name.partition(".")[0] in STDLIB_MODULES for name in imported_modules)
    assert violations == []


def test_mcp_integration_symbols_have_one_canonical_owner():
    expected_owners = {
        "MCP_TOOL_NAME_PREFIX": Path("core/contracts/mcp_tools.py"),
        "build_mcp_tool_name": Path("core/contracts/mcp_tools.py"),
        "is_mcp_tool_name": Path("integrations/mcp/naming.py"),
        "mcp_tool_display_name": Path("integrations/mcp/naming.py"),
        "mcp_tool_names": Path("integrations/mcp/naming.py"),
        "_mcp_lifecycle_error_result": Path("integrations/mcp/lifecycle.py"),
        "McpLifecycleService": Path("integrations/mcp/lifecycle.py"),
        "MCPSettingsError": Path("integrations/mcp/settings.py"),
        "MCPSettingsValidationError": Path("integrations/mcp/settings.py"),
        "MCPSettingsNotFound": Path("integrations/mcp/settings.py"),
        "TRANSPORT_TYPES": Path("integrations/mcp/settings.py"),
        "MCPSettingsService": Path("integrations/mcp/settings.py"),
        "_ReparentAsyncExitStack": Path("integrations/mcp/transport.py"),
        "MCPServerConnectionResult": Path("integrations/mcp/transport.py"),
        "MCPConnectionSummary": Path("integrations/mcp/transport.py"),
        "_http_url_transport_attempts": Path("integrations/mcp/transport.py"),
        "_use_implicit_http_transport_fallback": Path("integrations/mcp/transport.py"),
        "_mcp_connect_timeout_seconds": Path("integrations/mcp/transport.py"),
        "_open_mcp_transport": Path("integrations/mcp/transport.py"),
        "_connect_mcp_server_transport": Path("integrations/mcp/transport.py"),
        "_connect_mcp_servers_into_stack": Path("integrations/mcp/transport.py"),
        "connect_mcp_servers": Path("integrations/mcp/transport.py"),
        "MCPToolWrapper": Path("integrations/mcp/tool_adapter.py"),
        "register_mcp_server_tools": Path("integrations/mcp/tool_adapter.py"),
    }
    owners: dict[str, list[Path]] = {symbol: [] for symbol in expected_owners}

    for module_path in sorted(OPENSPRITE_ROOT.rglob("*.py")):
        tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
        relative_path = module_path.relative_to(OPENSPRITE_ROOT)
        for node in tree.body:
            declared_names: set[str] = set()
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                declared_names.add(node.name)
            elif isinstance(node, ast.Assign):
                declared_names.update(
                    name for target in node.targets for name in _assigned_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declared_names.update(_assigned_names(node.target))
            for name in expected_owners.keys() & declared_names:
                owners[name].append(relative_path)

    assert owners == {symbol: [path] for symbol, path in expected_owners.items()}


def test_mcp_settings_adapter_has_no_config_alias_and_explicit_dependencies():
    symbols = {
        "MCPSettingsError",
        "MCPSettingsValidationError",
        "MCPSettingsNotFound",
        "TRANSPORT_TYPES",
        "MCPSettingsService",
    }
    canonical_path = MCP_INTEGRATION_ROOT / "settings.py"
    legacy_module = "opensprite.config.mcp_settings"
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    dependency_violations: list[str] = []
    tree = ast.parse(canonical_path.read_text(encoding="utf-8-sig"), filename=str(canonical_path))
    allowed_packages = (
        "opensprite.config.defaults",
        "opensprite.config.json_files",
        "opensprite.config.schema",
    )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for imported_module in _imported_modules(canonical_path, node):
            if imported_module.partition(".")[0] in STDLIB_MODULES:
                continue
            if any(
                imported_module == allowed or imported_module.startswith(f"{allowed}.")
                for allowed in allowed_packages
            ):
                continue
            dependency_violations.append(f"{node.lineno}:{imported_module}")

    assert canonical_path.is_file()
    assert not (CONFIG_ROOT / "mcp_settings.py").exists()
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "integrations" / "mcp" / "test_mcp_settings.py").is_file()
    assert not (TESTS_ROOT / "config" / "test_mcp_settings.py").exists()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert dependency_violations == []
    assert violations == []


def test_mcp_tool_adapter_uses_the_canonical_tool_name_builder():
    module_path = MCP_INTEGRATION_ROOT / "tool_adapter.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))

    canonical_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and _resolved_import(module_path, node) == "opensprite.core.contracts.mcp_tools"
    ]
    imported_names = {
        alias.name
        for node in canonical_imports
        for alias in node.names
    }
    builder_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_mcp_tool_name"
    ]
    legacy_name_builders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        and any(
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.value.startswith("mcp_")
            for value in node.values
        )
    ]

    assert imported_names == {"build_mcp_tool_name"}
    assert len(builder_calls) == 3
    assert legacy_name_builders == []

    transport_path = MCP_INTEGRATION_ROOT / "transport.py"
    transport_tree = ast.parse(
        transport_path.read_text(encoding="utf-8-sig"),
        filename=str(transport_path),
    )
    transport_imports = {
        imported_module
        for node in ast.walk(transport_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_module in _imported_modules(transport_path, node)
    }
    transport_builder_calls = [
        node.lineno
        for node in ast.walk(transport_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_mcp_tool_name"
    ]
    transport_legacy_name_builders = [
        node.lineno
        for node in ast.walk(transport_tree)
        if isinstance(node, ast.JoinedStr)
        and any(
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.value.startswith("mcp_")
            for value in node.values
        )
    ]
    assert "opensprite.core.contracts.mcp_tools" not in transport_imports
    assert transport_builder_calls == []
    assert transport_legacy_name_builders == []


def test_mcp_tool_adapter_has_no_legacy_tools_module():
    canonical_module = "opensprite.integrations.mcp.tool_adapter"
    legacy_module = "opensprite.tools.mcp"
    symbols = {"MCPToolWrapper", "register_mcp_server_tools"}
    violations = [
        *_find_forbidden_imports(OPENSPRITE_ROOT, legacy_module),
        *_find_forbidden_imports(TESTS_ROOT, legacy_module),
    ]

    assert (MCP_INTEGRATION_ROOT / "tool_adapter.py").is_file()
    assert not (TOOLS_ROOT / "mcp.py").exists()
    assert _find_spec_or_none(canonical_module) is not None
    assert _find_spec_or_none(legacy_module) is None
    assert (TESTS_ROOT / "integrations" / "mcp" / "test_tool_adapter.py").is_file()
    assert not (TESTS_ROOT / "tools" / "test_mcp.py").exists()
    for initializer in sorted(OPENSPRITE_ROOT.rglob("__init__.py")):
        assert symbols.isdisjoint(_top_level_bound_names(initializer))
    assert violations == []


def test_mcp_integration_adapters_are_not_reexported_from_tools():
    integration_symbols = {
        "_ReparentAsyncExitStack",
        "MCPConnectionSummary",
        "MCPServerConnectionResult",
        "_http_url_transport_attempts",
        "_use_implicit_http_transport_fallback",
        "_mcp_connect_timeout_seconds",
        "_open_mcp_transport",
        "_connect_mcp_server_transport",
        "_connect_mcp_servers_into_stack",
        "connect_mcp_servers",
        "MCPToolWrapper",
        "register_mcp_server_tools",
    }
    assert not (TOOLS_ROOT / "mcp.py").exists()

    violations = [
        *_find_forbidden_imports(TOOLS_MODULE_ROOT, "opensprite.integrations.mcp.tool_adapter"),
        *_find_forbidden_imports(TOOLS_MODULE_ROOT, "opensprite.integrations.mcp.transport"),
    ]
    assert violations == [], f"tools module must not depend on MCP integration adapters: {violations}"

    legacy_imports: list[str] = []
    for package_root in (OPENSPRITE_ROOT, TESTS_ROOT):
        for module_path in sorted(package_root.rglob("*.py")):
            tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if _resolved_import(module_path, node) not in {
                    "opensprite.tools",
                    "opensprite.tools.mcp",
                }:
                    continue
                imported_names = {alias.name for alias in node.names}
                if integration_symbols & imported_names or "*" in imported_names:
                    legacy_imports.append(f"{module_path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert legacy_imports == [], f"MCP integration must use its canonical modules: {legacy_imports}"


def test_mcp_tests_follow_production_ownership():
    tool_adapter_test = TESTS_ROOT / "integrations" / "mcp" / "test_tool_adapter.py"
    transport_test = TESTS_ROOT / "integrations" / "mcp" / "test_transport.py"
    assert tool_adapter_test.is_file()
    assert transport_test.is_file()
    assert not (TESTS_ROOT / "tools" / "test_mcp.py").exists()

    tool_adapter_test_bindings = _top_level_bound_names(tool_adapter_test)
    transport_test_bindings = _top_level_bound_names(transport_test)
    assert "connect_mcp_servers" not in tool_adapter_test_bindings
    assert {"MCPToolWrapper", "register_mcp_server_tools"}.issubset(tool_adapter_test_bindings)
    assert "connect_mcp_servers" in transport_test_bindings
