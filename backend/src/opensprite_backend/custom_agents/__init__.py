"""Validated definitions for OpenSprite custom Agents."""

from .definition import (
    AgentDefinition,
    AgentDefinitionError,
    MAX_DEFINITION_BYTES,
    parse_agent_definition,
)

__all__ = [
    "AgentDefinition",
    "AgentDefinitionError",
    "MAX_DEFINITION_BYTES",
    "parse_agent_definition",
]
