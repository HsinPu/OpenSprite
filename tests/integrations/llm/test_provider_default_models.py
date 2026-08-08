import pytest

from opensprite.integrations.llm.minimax.chat import MiniMaxLLM
from opensprite.integrations.llm.openai.chat import OpenAILLM
from opensprite.integrations.llm.openai.responses import OpenAIResponsesLLM
from opensprite.integrations.llm.openrouter.chat import OpenRouterLLM


@pytest.mark.parametrize(
    "provider_type",
    (OpenAILLM, OpenAIResponsesLLM, OpenRouterLLM, MiniMaxLLM),
)
def test_provider_owns_default_model_contract(provider_type):
    provider = provider_type.__new__(provider_type)
    provider.default_model = "configured-model"

    assert provider.get_default_model() == "configured-model"
