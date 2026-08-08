import asyncio

from opensprite.app.llm_fallback import UnconfiguredLLM


def test_unconfigured_llm_returns_stable_empty_response():
    provider = UnconfiguredLLM()

    response = asyncio.run(provider.chat([]))

    assert provider.get_default_model() == "unconfigured"
    assert response.content == ""
    assert response.model == "unconfigured"
