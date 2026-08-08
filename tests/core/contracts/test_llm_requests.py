from opensprite.core.contracts.llm_requests import LLMRequestMode, resolve_response_format


def test_resolve_response_format_uses_explicit_format_only():
    explicit = {"type": "json_schema", "name": "custom"}

    assert resolve_response_format(explicit, LLMRequestMode.MAIN_CHAT) is explicit
    assert resolve_response_format(explicit, "custom") is explicit
    assert resolve_response_format(None, LLMRequestMode.MAIN_CHAT) is None
