from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from opensprite_backend.provider_identity import ProviderId


@pytest.mark.parametrize("value", ["openai", "anthropic", "openrouter", str(uuid4())])
def test_provider_id_accepts_builtin_and_custom(value):
    assert TypeAdapter(ProviderId).validate_python(value) == value


@pytest.mark.parametrize("value", [1, True, "", "custom", "../auth", None,
    "00000000-0000-0000-0000-000000000000", "6ba7b810-9dad-11d1-80b4-00c04fd430c8"])
def test_provider_id_rejects_invalid(value):
    with pytest.raises(ValidationError):
        TypeAdapter(ProviderId).validate_python(value)
