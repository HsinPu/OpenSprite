import httpx
import pytest

from opensprite_backend.models import ErrorCode
from opensprite_backend.providers.adapters import ProviderValidationError
from opensprite_backend.providers.direct_models import DirectModelDiscovery


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_openai_filters_non_text_models_and_preserves_known_capacity():
    def handle(request):
        assert request.url == "https://api.openai.com/v1/models"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={"data": [{"id": value} for value in (
            "gpt-5.6", "gpt-future", "text-embedding-3-small", "gpt-image-1",
            "gpt-4o-realtime-preview", "whisper-1", "gpt-future",
        )]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = await DirectModelDiscovery(client).list_models("openai", "secret")
    by_id = {model.model_id: model for model in models}
    assert set(by_id) == {"gpt-5.6", "gpt-future"}
    assert by_id["gpt-5.6"].context_window_tokens == 1_050_000
    assert by_id["gpt-future"].context_window_tokens == 8192
    assert by_id["gpt-future"].max_output_tokens == 2048
    assert by_id["gpt-future"].supports_tools is False


@pytest.mark.anyio
async def test_anthropic_follows_cursor_and_deduplicates():
    calls = []
    def handle(request):
        calls.append(request)
        assert request.headers["x-api-key"] == "secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        if len(calls) == 1:
            return httpx.Response(200, json={"data": [{"id": "claude-a", "display_name": "A"}], "has_more": True, "last_id": "claude-a"})
        assert request.url.params["after_id"] == "claude-a"
        return httpx.Response(200, json={"data": [{"id": "claude-a"}, {"id": "claude-b"}], "has_more": False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        models = await DirectModelDiscovery(client).list_models("anthropic", "secret")
    assert {model.model_id for model in models} == {"claude-a", "claude-b"}
    assert len(calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("status,code", [(401, ErrorCode.INVALID_CREDENTIALS), (429, ErrorCode.PROVIDER_RATE_LIMITED), (302, ErrorCode.PROVIDER_UNREACHABLE)])
async def test_sanitizes_errors_without_following_redirects(status, code):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, text="secret", headers={"location": "https://elsewhere.invalid"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderValidationError) as failure:
            await DirectModelDiscovery(client).list_models("openai", "secret")
    assert failure.value.code == code
    assert "secret" not in str(failure.value)
    assert len(calls) == 1


@pytest.mark.anyio
async def test_repeated_cursor_fails_instead_of_returning_partial_catalog():
    def handle(request):
        return httpx.Response(200, json={"data": [{"id": "claude-a"}], "has_more": True, "last_id": "claude-a"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderValidationError):
            await DirectModelDiscovery(client).list_models("anthropic", "secret")


@pytest.mark.anyio
async def test_total_response_byte_limit(monkeypatch):
    monkeypatch.setattr("opensprite_backend.providers.direct_models.MAX_RESPONSE_BYTES", 10)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "gpt-future"}]}))) as client:
        with pytest.raises(ProviderValidationError):
            await DirectModelDiscovery(client).list_models("openai", "secret")
