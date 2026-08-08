from opensprite.modules.llm.reasoning import (
    is_valid_reasoning_effort,
    normalize_reasoning_effort,
    reasoning_config_from_effort,
    reasoning_config_or_default,
    reasoning_effort_from_config,
)


def test_reasoning_effort_helpers_normalize_supported_modes():
    assert normalize_reasoning_effort(" HIGH ") == "high"
    assert normalize_reasoning_effort("unknown") == ""
    assert is_valid_reasoning_effort("xhigh") is True
    assert is_valid_reasoning_effort("turbo") is False
    assert reasoning_config_from_effort("") is None
    assert reasoning_config_from_effort("none") == {"enabled": False}
    assert reasoning_config_from_effort("low") == {"enabled": True, "effort": "low"}


def test_reasoning_config_or_default_preserves_explicit_modes():
    assert reasoning_config_or_default("") == {"enabled": True}
    assert reasoning_config_or_default("none") == {"enabled": False}
    assert reasoning_config_or_default("high") == {"enabled": True, "effort": "high"}


def test_reasoning_effort_from_config_handles_disabled_explicit_and_default_modes():
    assert reasoning_effort_from_config(None) is None
    assert reasoning_effort_from_config({"enabled": False}) == "none"
    assert reasoning_effort_from_config({"enabled": False}, allow_none=False) is None
    assert reasoning_effort_from_config({"enabled": True, "effort": " HIGH "}) == "high"
    assert reasoning_effort_from_config({"enabled": True}) == "medium"
    assert reasoning_effort_from_config({"enabled": True}, default="low") == "low"
    assert reasoning_effort_from_config({"enabled": True}, default="invalid") == "medium"
