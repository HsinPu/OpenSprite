"""Tool contracts and the supported strict JSON-schema subset."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from opensprite_backend.workspaces import (
    UNASSIGNED_WORKSPACE_ID,
    UnassignedWorkspaceResolver,
    WorkspaceExecutionContext,
)


_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ARGUMENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_SCHEMA_TYPES = {"string", "integer", "number", "boolean", "object", "array"}
_COMMON_SCHEMA_KEYS = {"type", "description", "enum"}


class ToolEffect(str, Enum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    EXTERNAL_WRITE = "external_write"
    DESTRUCTIVE = "destructive"
    SENSITIVE = "sensitive"


class ToolSource(str, Enum):
    BUILTIN = "builtin"
    MCP = "mcp"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]
    effect: ToolEffect
    source: ToolSource = ToolSource.BUILTIN
    source_id: str | None = None
    display_name: str | None = None
    timeout_seconds: float = 10
    max_output_chars: int = 8192

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _TOOL_NAME.fullmatch(self.name) is None:
            raise ValueError("invalid tool name")
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
            or len(self.description) > 1024
        ):
            raise ValueError("invalid tool description")
        if not isinstance(self.effect, ToolEffect):
            raise ValueError("invalid tool effect")
        if not isinstance(self.source, ToolSource):
            raise ValueError("invalid tool source")
        if self.source is ToolSource.MCP:
            if not isinstance(self.source_id, str) or not self.source_id:
                raise ValueError("MCP tool requires source id")
        elif self.source_id is not None:
            raise ValueError("non-MCP tool cannot have source id")
        if self.display_name is not None and (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
            or len(self.display_name) > 256
        ):
            raise ValueError("invalid tool display name")
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or not 0 < self.timeout_seconds <= 60
        ):
            raise ValueError("invalid tool timeout")
        if (
            not isinstance(self.max_output_chars, int)
            or isinstance(self.max_output_chars, bool)
            or not 1 <= self.max_output_chars <= 65536
        ):
            raise ValueError("invalid tool output cap")
        _validate_schema(self.input_schema, root=True)
        encoded = json.dumps(
            self.input_schema,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > 32768:
            raise ValueError("tool schema is too large")


@dataclass(frozen=True, slots=True)
class ToolContext:
    run_id: str
    conversation_id: str
    cancellation_event: asyncio.Event
    workspace: WorkspaceExecutionContext = field(
        default_factory=lambda: UnassignedWorkspaceResolver().execution_context(
            UNASSIGNED_WORKSPACE_ID
        )
    )


@dataclass(frozen=True, slots=True)
class ToolResult:
    content: str
    summary: str


class Tool(Protocol):
    definition: ToolDefinition

    async def invoke(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult: ...


def validate_arguments(
    schema: dict[str, object],
    arguments: dict[str, object],
) -> bool:
    try:
        return _matches_schema(schema, arguments)
    except (TypeError, ValueError):
        return False


def _validate_schema(schema: object, *, root: bool = False) -> None:
    if not isinstance(schema, dict):
        raise ValueError("tool schema must be an object")
    schema_type = schema.get("type")
    if schema_type not in _SCHEMA_TYPES:
        raise ValueError("unsupported tool schema type")
    allowed = set(_COMMON_SCHEMA_KEYS)
    if schema_type == "string":
        allowed.update({"minLength", "maxLength"})
    elif schema_type in {"integer", "number"}:
        allowed.update({"minimum", "maximum"})
    elif schema_type == "array":
        allowed.update({"items", "minItems", "maxItems"})
    elif schema_type == "object":
        allowed.update({"properties", "required", "additionalProperties"})
    if set(schema) - allowed:
        raise ValueError("unsupported tool schema keyword")
    description = schema.get("description")
    if description is not None and (
        not isinstance(description, str) or len(description) > 1024
    ):
        raise ValueError("invalid schema description")
    enum = schema.get("enum")
    if enum is not None and (
        not isinstance(enum, list)
        or not enum
        or len(enum) > 100
        or len({json.dumps(item, sort_keys=True) for item in enum}) != len(enum)
    ):
        raise ValueError("invalid schema enum")
    if schema_type == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        if (
            not isinstance(properties, dict)
            or len(properties) > 32
            or not isinstance(required, list)
            or any(not isinstance(item, str) for item in required)
            or len(set(required)) != len(required)
            or not set(required).issubset(properties)
            or schema.get("additionalProperties") is not False
        ):
            raise ValueError("object schemas must be strict")
        for name, child in properties.items():
            if not isinstance(name, str) or _ARGUMENT_NAME.fullmatch(name) is None:
                raise ValueError("invalid tool argument name")
            _validate_schema(child)
    elif root:
        raise ValueError("tool input schema root must be an object")
    elif schema_type == "array":
        _validate_schema(schema.get("items"))
        _validate_integer_bounds(schema, "minItems", "maxItems", 0, 1000)
    elif schema_type == "string":
        _validate_integer_bounds(schema, "minLength", "maxLength", 0, 32768)
    elif schema_type in {"integer", "number"}:
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        for value in (minimum, maximum):
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                raise ValueError("invalid numeric bound")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("numeric bounds are inverted")


def _validate_integer_bounds(
    schema: dict[str, object],
    minimum_name: str,
    maximum_name: str,
    floor: int,
    ceiling: int,
) -> None:
    minimum = schema.get(minimum_name, floor)
    maximum = schema.get(maximum_name, ceiling)
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or not floor <= minimum <= maximum <= ceiling
    ):
        raise ValueError("invalid schema length bound")


def _matches_schema(schema: dict[str, object], value: object) -> bool:
    schema_type = schema["type"]
    if schema_type == "string":
        if not isinstance(value, str):
            return False
        if not int(schema.get("minLength", 0)) <= len(value) <= int(
            schema.get("maxLength", 32768)
        ):
            return False
    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if "minimum" in schema and value < schema["minimum"]:
            return False
        if "maximum" in schema and value > schema["maximum"]:
            return False
    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        if "minimum" in schema and value < schema["minimum"]:
            return False
        if "maximum" in schema and value > schema["maximum"]:
            return False
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            return False
    elif schema_type == "array":
        if not isinstance(value, list):
            return False
        if not int(schema.get("minItems", 0)) <= len(value) <= int(
            schema.get("maxItems", 1000)
        ):
            return False
        item_schema = schema["items"]
        if not isinstance(item_schema, dict) or not all(
            _matches_schema(item_schema, item) for item in value
        ):
            return False
    elif schema_type == "object":
        if not isinstance(value, dict):
            return False
        properties = schema["properties"]
        required = schema["required"]
        if not isinstance(properties, dict) or not isinstance(required, list):
            return False
        if not set(required).issubset(value) or not set(value).issubset(properties):
            return False
        for name, item in value.items():
            child = properties[name]
            if not isinstance(child, dict) or not _matches_schema(child, item):
                return False
    else:
        return False
    enum = schema.get("enum")
    return enum is None or value in enum
