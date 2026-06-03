from opensprite.llms.base import UNCONFIGURED_LLM_MODEL, UnconfiguredLLM, is_unconfigured_llm


def test_is_unconfigured_llm_detects_fallback_provider_and_model_marker():
    assert is_unconfigured_llm(None, "any-model") is True
    assert is_unconfigured_llm(UnconfiguredLLM(), "custom") is True
    assert is_unconfigured_llm(object(), f" {UNCONFIGURED_LLM_MODEL.upper()} ") is True
    assert is_unconfigured_llm(object(), "configured-model") is False


def test_unconfigured_llm_default_model_uses_shared_marker():
    assert UnconfiguredLLM().get_default_model() == UNCONFIGURED_LLM_MODEL
