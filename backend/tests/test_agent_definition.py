import hashlib

import pytest

from opensprite_backend.custom_agents import (
    AgentDefinition,
    AgentDefinitionError,
    MAX_DEFINITION_BYTES,
    parse_agent_definition,
)


BASE = b'''name = "code-review"
description = "Check correctness and maintainability."
developer_instructions = """
Review code using evidence and report actionable findings.
"""
'''


def parse_error(content: bytes) -> AgentDefinitionError:
    with pytest.raises(AgentDefinitionError) as caught:
        parse_agent_definition(content)
    return caught.value


def test_parses_definition_and_hashes_original_bytes() -> None:
    definition = parse_agent_definition(BASE)

    assert isinstance(definition, AgentDefinition)
    assert definition.name == "code-review"
    assert definition.name_key == "code-review"
    assert definition.description == "Check correctness and maintainability."
    assert "Review code" in definition.developer_instructions
    assert definition.content_hash == hashlib.sha256(BASE).hexdigest()
    assert "Review code" not in repr(definition)


def test_normalises_name_and_name_key() -> None:
    definition = parse_agent_definition(
        BASE.replace(b'"code-review"', ' " e\u0301quipe "'.encode("utf-8"))
    )

    assert definition.name == "équipe"
    assert definition.name_key == "équipe"


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("name", "invalid_name"),
        ("description", "invalid_description"),
        ("developer_instructions", "invalid_developer_instructions"),
    ],
)
def test_required_fields_must_be_non_empty_strings(field: str, code: str) -> None:
    lines = [
        'name = "code-review"',
        'description = "description"',
        'developer_instructions = "instructions"',
    ]
    index = next(index for index, line in enumerate(lines) if line.startswith(field))
    lines[index] = f'{field} = ""'
    assert parse_error("\n".join(lines).encode()).code == code


@pytest.mark.parametrize(
    "content",
    [
        BASE.replace(b'name = "code-review"', b"name = 42"),
        BASE.replace(b'description = "Check correctness and maintainability."', b"description = true"),
        BASE.replace(b'developer_instructions = """', b"developer_instructions = []"),
    ],
)
def test_fields_reject_toml_type_mismatches(content: bytes) -> None:
    assert parse_error(content).code.startswith("invalid_")


@pytest.mark.parametrize(
    "content",
    [
        BASE.replace(b'developer_instructions = """', b"extra = true\ndeveloper_instructions = \"\"\""),
        BASE + b'unknown = "field"\n',
    ],
)
def test_unknown_fields_are_rejected(content: bytes) -> None:
    assert parse_error(content).code == "unknown_field"


def test_duplicate_fields_are_rejected_without_source_in_error() -> None:
    error = parse_error(BASE + b'name = "other"\n')

    assert error.code == "duplicate_field"
    assert "code-review" not in str(error)
    assert "Review code" not in repr(error)


def test_optional_provider_and_model_must_be_a_non_empty_pair() -> None:
    provider_only = BASE + b'provider_id = "openrouter"\n'
    model_only = BASE + b'model = "openrouter/auto"\n'
    blank_pair = BASE + b'provider_id = " "\nmodel = "model"\n'

    assert parse_error(provider_only).code == "provider_model_pair_required"
    assert parse_error(model_only).code == "provider_model_pair_required"
    assert parse_error(blank_pair).code == "invalid_provider_id"

    complete = BASE + b'provider_id = "openrouter"\nmodel = "openrouter/auto"\n'
    definition = parse_agent_definition(complete)
    assert definition.provider_id == "openrouter"
    assert definition.model == "openrouter/auto"


def test_invalid_utf8_and_size_are_safe_errors() -> None:
    assert parse_error(b"\xff").code == "invalid_utf8"
    assert parse_error(b"x" * (MAX_DEFINITION_BYTES + 1)).code == "content_too_large"
    assert "x" * 100 not in str(parse_error(b"x" * (MAX_DEFINITION_BYTES + 1)))


def test_parser_requires_bytes() -> None:
    assert parse_error("name = 'x'".encode()).code == "missing_field"
    with pytest.raises(AgentDefinitionError) as caught:
        parse_agent_definition("not bytes")  # type: ignore[arg-type]
    assert caught.value.code == "invalid_content"


def test_definition_is_immutable() -> None:
    definition = parse_agent_definition(BASE)
    with pytest.raises(AttributeError):
        definition.name = "other"  # type: ignore[misc]
