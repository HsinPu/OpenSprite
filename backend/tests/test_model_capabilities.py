import pytest

from opensprite_backend.inference.capabilities import (
    ModelCapability,
    fixed_model_capability,
    fixed_model_catalog,
)


def test_fixed_catalog_uses_verified_direct_provider_models() -> None:
    assert [item.model_id for item in fixed_model_catalog("openai")] == [
        "gpt-5.6",
        "gpt-5.6-luna",
    ]
    assert [item.model_id for item in fixed_model_catalog("anthropic")] == [
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    ]
    assert fixed_model_catalog("openrouter") == ()

    sonnet = fixed_model_capability("anthropic", "claude-sonnet-4-6")
    assert sonnet is not None
    assert sonnet.context_window_tokens == 1_000_000
    assert sonnet.max_output_tokens == 128_000
    assert fixed_model_capability("openai", "unknown") is None


@pytest.mark.parametrize(
    ("context_window", "max_output"),
    [(0, 1), (100, 0), (100, 101)],
)
def test_capability_rejects_impossible_token_limits(
    context_window: int,
    max_output: int,
) -> None:
    with pytest.raises(ValueError):
        ModelCapability(
            provider_id="openai",
            model_id="test",
            name="Test",
            context_window_tokens=context_window,
            max_output_tokens=max_output,
        )
