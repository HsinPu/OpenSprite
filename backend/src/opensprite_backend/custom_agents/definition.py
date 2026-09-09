"""Strict, immutable definitions for user-provided subagents.

Agent definition files are deliberately limited to a small TOML contract.  This
module only parses and validates that contract; persistence, discovery, policy,
and subagent execution belong to later custom-agent layers.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from typing import Final


MAX_DEFINITION_BYTES: Final = 64 * 1024
_ALLOWED_FIELDS: Final = frozenset(
    {"name", "description", "developer_instructions", "provider_id", "model"}
)
_CONTROL_CATEGORIES: Final = frozenset({"Cc", "Cs"})
_EMPTY = re.compile(r"^\s*$")


class AgentDefinitionError(ValueError):
    """Safe validation failure for an Agent definition.

    The exception intentionally exposes only a stable error code.  In
    particular, it never includes the source TOML, developer instructions, or
    parser details that could echo user-controlled content into logs or an API
    response.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """The validated, immutable subset of an Agent TOML definition."""

    name: str
    description: str
    developer_instructions: str = field(repr=False)
    provider_id: str | None = None
    model: str | None = None
    # Keep the public constructor's optional provider/model arguments in their
    # natural order while requiring the parser-owned hash by keyword.
    content_hash: str = field(repr=False, kw_only=True)
    name_key: str = field(init=False)

    def __post_init__(self) -> None:
        name = _normalise_name(self.name)
        description = _required_text(self.description, "invalid_description")
        instructions = _required_text(
            self.developer_instructions, "invalid_developer_instructions"
        )
        provider_id = _optional_text(self.provider_id, "invalid_provider_id")
        model = _optional_text(self.model, "invalid_model")
        if (provider_id is None) != (model is None):
            raise AgentDefinitionError("provider_model_pair_required")

        if (
            type(self.content_hash) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.content_hash) is None
        ):
            raise AgentDefinitionError("invalid_content_hash")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "developer_instructions", instructions)
        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "name_key", name.casefold())


def parse_agent_definition(content: bytes) -> AgentDefinition:
    """Parse a strict Agent TOML document from its original UTF-8 bytes.

    The returned hash is calculated before decoding and therefore covers the
    exact bytes supplied by the caller, including line endings or a UTF-8 BOM.
    All failures are converted into :class:`AgentDefinitionError` without
    retaining parser messages or source content.
    """

    if type(content) is not bytes:
        raise AgentDefinitionError("invalid_content")
    if len(content) > MAX_DEFINITION_BYTES:
        raise AgentDefinitionError("content_too_large")
    content_hash = hashlib.sha256(content).hexdigest()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise AgentDefinitionError("invalid_utf8") from None

    try:
        values = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        # tomllib's diagnostic contains a source location but no source text;
        # still collapse it to a stable safe code for callers.
        message = str(error).lower()
        code = (
            "duplicate_field"
            if "overwrite" in message or "redefin" in message
            else "invalid_format"
        )
        raise AgentDefinitionError(code) from None
    except (TypeError, ValueError, RecursionError):
        raise AgentDefinitionError("invalid_format") from None

    if type(values) is not dict:
        raise AgentDefinitionError("invalid_format")
    unknown = set(values) - _ALLOWED_FIELDS
    if unknown:
        raise AgentDefinitionError("unknown_field")
    if not {"name", "description", "developer_instructions"}.issubset(values):
        raise AgentDefinitionError("missing_field")

    name = values["name"]
    description = values["description"]
    instructions = values["developer_instructions"]
    if type(name) is not str:
        raise AgentDefinitionError("invalid_name")
    if type(description) is not str:
        raise AgentDefinitionError("invalid_description")
    if type(instructions) is not str:
        raise AgentDefinitionError("invalid_developer_instructions")

    provider_id = values.get("provider_id")
    model = values.get("model")
    if provider_id is not None and type(provider_id) is not str:
        raise AgentDefinitionError("invalid_provider_id")
    if model is not None and type(model) is not str:
        raise AgentDefinitionError("invalid_model")

    try:
        return AgentDefinition(
            name=name,
            description=description,
            developer_instructions=instructions,
            provider_id=provider_id,
            model=model,
            content_hash=content_hash,
        )
    except AgentDefinitionError:
        raise
    except (TypeError, ValueError):
        raise AgentDefinitionError("invalid_format") from None


def _normalise_name(value: object) -> str:
    if type(value) is not str:
        raise AgentDefinitionError("invalid_name")
    value = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(value) <= 80 or _EMPTY.fullmatch(value):
        raise AgentDefinitionError("invalid_name")
    if any(unicodedata.category(char) in _CONTROL_CATEGORIES for char in value):
        raise AgentDefinitionError("invalid_name")
    return value


def _required_text(value: object, code: str) -> str:
    if type(value) is not str:
        raise AgentDefinitionError(code)
    value = value.strip()
    if not value:
        raise AgentDefinitionError(code)
    return value


def _optional_text(value: object, code: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise AgentDefinitionError(code)
    value = value.strip()
    if not value:
        raise AgentDefinitionError(code)
    return value
