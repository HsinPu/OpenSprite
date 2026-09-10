"""Bounded model discovery for configured Chat Completions endpoints."""

import json

import httpx

from .catalog_models import ProviderEndpointSnapshot
from .catalog_store import CatalogError


async def discover_models(client: httpx.AsyncClient, endpoint: ProviderEndpointSnapshot, api_key: str | None) -> list[str]:
    headers = {"Accept": "application/json"}
    if endpoint.auth_mode == "bearer":
        if not api_key:
            raise CatalogError("not_connected")
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with client.stream("GET", endpoint.endpoint("models"), headers=headers, follow_redirects=False, timeout=30.0) as response:
            if response.status_code in (401, 403):
                raise CatalogError("invalid_credentials")
            if response.status_code == 429:
                raise CatalogError("provider_rate_limited")
            if response.status_code == 404:
                raise CatalogError("model_discovery_unsupported")
            if response.status_code != 200:
                raise CatalogError("provider_unreachable")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 4 * 1024 * 1024:
                    raise CatalogError("invalid_provider_response")
            body = json.loads(data)
            if type(body) is not dict or type(body.get("data")) is not list:
                raise CatalogError("invalid_provider_response")
            ids: dict[str, None] = {}
            for item in body["data"]:
                if type(item) is not dict:
                    raise CatalogError("invalid_provider_response")
                model_id = item.get("id")
                if type(model_id) is not str or not 1 <= len(model_id) <= 256 or model_id != model_id.strip() or any(ord(c) < 32 for c in model_id):
                    raise CatalogError("invalid_provider_response")
                ids[model_id] = None
            return list(ids)
    except CatalogError:
        raise
    except httpx.TimeoutException:
        raise CatalogError("provider_timeout") from None
    except httpx.HTTPError:
        raise CatalogError("provider_unreachable") from None
    except (ValueError, UnicodeError):
        raise CatalogError("invalid_provider_response") from None
    finally:
        headers.pop("Authorization", None)
        api_key = None
