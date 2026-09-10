import httpx
import pytest

from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
from opensprite_backend.providers.catalog_store import CatalogError
from opensprite_backend.providers.custom_discovery import discover_models


def endpoint(auth="none"):
    return ProviderEndpointSnapshot("test", 1, "openai_chat_completions", "https://example.com/v1", auth)


@pytest.mark.anyio
async def test_discovery_deduplicates_and_keeps_prefix():
    def handler(request):
        assert str(request.url) == "https://example.com/v1/models"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "a"}, {"id": "b"}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await discover_models(client, endpoint(), None) == ["a", "b"]


@pytest.mark.anyio
async def test_redirect_is_not_followed():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example/models"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(CatalogError, match="provider_unreachable"):
            await discover_models(client, endpoint("bearer"), "private-key")
    assert len(calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("status,code", [(401,"invalid_credentials"),(429,"provider_rate_limited"),(404,"model_discovery_unsupported"),(500,"provider_unreachable")])
async def test_safe_errors(status, code):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, text="secret upstream details"))) as client:
        with pytest.raises(CatalogError, match=code) as error:
            await discover_models(client, endpoint(), None)
        assert "secret" not in str(error.value)
