"""Custom-provider catalog endpoints under the default authenticated API boundary."""

import asyncio
import json
import re
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opensprite_backend.providers.catalog_store import CatalogError, CustomModel, _strict_pairs
from opensprite_backend.providers.custom_service import CustomProviderService
from .custom_provider_models import ProviderCreateRequest
from .custom_provider_models import ProviderUpdateRequest
from .custom_provider_models import ProviderModelRequest, ProviderRevisionRequest

router = APIRouter()


def service(request: Request) -> CustomProviderService:
    value = getattr(request.app.state, "custom_providers", None)
    if value is None:
        raise CatalogError()
    return value


def error_response(error: CatalogError) -> JSONResponse:
    status = {"invalid_request": 400, "duplicate_name": 409, "revision_conflict": 409,
              "provider_not_found": 404, "credential_required": 400,
              "duplicate_model": 409, "model_not_found": 404,
              "provider_busy": 409, "provider_in_use": 409, "not_connected": 409,
              "invalid_credentials": 422, "provider_rate_limited": 429,
              "model_discovery_unsupported": 422, "provider_unreachable": 502,
              "invalid_provider_response": 502, "provider_timeout": 504}.get(error.code, 503)
    return JSONResponse(status_code=status, content={"error": {"code": error.code, "message": "Provider operation failed.", "retryable": status in {429, 502, 503, 504}}})


def mutations(request: Request):
    value = getattr(request.app.state, "provider_mutations", None)
    if value is None:
        raise CatalogError()
    return value


async def mutation_body(request: Request, schema):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise CatalogError("invalid_request")
    try:
        return schema.model_validate(json.loads(body, object_pairs_hook=_strict_pairs))
    except ValueError:
        raise CatalogError("invalid_request") from None


def delete_revision(request: Request) -> int:
    pairs = list(request.query_params.multi_items())
    if len(pairs) != 1 or pairs[0][0] != "expectedRevision":
        raise CatalogError("invalid_request")
    raw = pairs[0][1]
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 16 or int(raw) < 1:
        raise CatalogError("invalid_request")
    return int(raw)


@router.put("/api/providers/{provider_id}", operation_id="updateProvider")
async def update_custom_provider(provider_id: str, request: Request):
    try:
        payload = await mutation_body(request, ProviderUpdateRequest)
        result = await mutations(request).update(provider_id, name=payload.name,
            base_url=payload.baseUrl, auth_mode=payload.authMode, allow_insecure_local=payload.allowInsecureLocal,
            expected_revision=payload.expectedRevision, secret=payload.apiKey.get_secret_value() if payload.apiKey else None)
        return result.model_dump(mode="json")
    except CatalogError as error:
        return error_response(error)


@router.delete("/api/providers/{provider_id}", operation_id="deleteProvider")
async def delete_custom_provider(provider_id: str, request: Request):
    try:
        await mutations(request).delete(provider_id, expected_revision=delete_revision(request))
        return {"deleted": True}
    except CatalogError as error:
        return error_response(error)


@router.put("/api/providers/{provider_id}/models/{model_key}", operation_id="updateProviderModel")
async def update_custom_model(provider_id: str, model_key: str, request: Request):
    try:
        payload = await mutation_body(request, ProviderModelRequest)
        try:
            model = CustomModel(key=model_key, model_id=payload.modelId, name=payload.name,
                context_limit=payload.contextLimit, output_limit=payload.outputLimit, tools=payload.tools, source="manual")
        except ValueError:
            raise CatalogError("invalid_request") from None
        result = await mutations(request).update_model(provider_id, model, expected_revision=payload.expectedRevision)
        return {"revision": result.revision, "models": [item.model_dump(mode="json") for item in result.models]}
    except CatalogError as error:
        return error_response(error)


@router.delete("/api/providers/{provider_id}/models/{model_key}", operation_id="deleteProviderModel")
async def delete_custom_model(provider_id: str, model_key: str, request: Request):
    try:
        result = await mutations(request).delete_model(provider_id, model_key, expected_revision=delete_revision(request))
        return {"revision": result.revision, "models": [item.model_dump(mode="json") for item in result.models]}
    except CatalogError as error:
        return error_response(error)


@router.post("/api/providers", status_code=201, operation_id="createProvider")
async def create_provider(request: Request):
    try:
        payload = await mutation_body(request, ProviderCreateRequest)
        result = await asyncio.to_thread(service(request).save, provider_id=None, name=payload.name,
            base_url=payload.baseUrl, auth_mode=payload.authMode, allow_insecure_local=payload.allowInsecureLocal,
            expected_revision=payload.expectedRevision, secret=payload.apiKey.get_secret_value() if payload.apiKey else None)
        return JSONResponse(status_code=201, content=result.model_dump(mode="json"))
    except CatalogError as error:
        return error_response(error)


@router.get("/api/providers/catalog", operation_id="getProviderCatalog")
async def get_custom_catalog(request: Request):
    try:
        pairs = list(request.query_params.multi_items())
        if any(key not in {"limit", "cursor"} for key, _ in pairs) or len({key for key, _ in pairs}) != len(pairs):
            raise CatalogError("invalid_request")
        limit_text = request.query_params.get("limit", "50")
        if not re.fullmatch(r"[1-9][0-9]{0,2}", limit_text) or int(limit_text) > 100:
            raise CatalogError("invalid_request")
        limit = int(limit_text)
        result = await asyncio.to_thread(service(request).list)
        offset = 0
        cursor = request.query_params.get("cursor")
        if cursor is not None:
            match = re.fullmatch(r"([0-9]{1,16}):([1-9][0-9]{0,15})", cursor)
            if match is None:
                raise CatalogError("invalid_request")
            if int(match[1]) != result.revision:
                raise CatalogError("revision_conflict")
            offset = int(match[2])
            if offset >= len(result.providers):
                raise CatalogError("invalid_request")
        page = result.providers[offset:offset + limit]
        next_offset = offset + len(page)
        return {"revision": result.revision, "providers": [item.model_dump(mode="json") for item in page],
                "nextCursor": f"{result.revision}:{next_offset}" if next_offset < len(result.providers) else None}
    except CatalogError as error:
        return error_response(error)


@router.get("/api/providers/{provider_id}", operation_id="getProvider")
async def get_custom_provider(provider_id: str, request: Request):
    try:
        result = await asyncio.to_thread(service(request).get, provider_id)
        return result.model_dump(mode="json")
    except CatalogError as error:
        return error_response(error)


@router.get("/api/providers/{provider_id}/models", operation_id="listProviderModels")
async def get_custom_models(provider_id: str, request: Request):
    try:
        pairs = list(request.query_params.multi_items())
        if any(key not in {"limit", "cursor"} for key, _ in pairs) or len({key for key, _ in pairs}) != len(pairs):
            raise CatalogError("invalid_request")
        limit_text = request.query_params.get("limit", "50")
        if not re.fullmatch(r"[1-9][0-9]{0,2}", limit_text) or int(limit_text) > 100:
            raise CatalogError("invalid_request")
        result = await asyncio.to_thread(service(request).get, provider_id)
        offset = 0
        cursor = request.query_params.get("cursor")
        if cursor is not None:
            match = re.fullmatch(r"([0-9]{1,16}):([1-9][0-9]{0,15})", cursor)
            if match is None:
                raise CatalogError("invalid_request")
            if int(match[1]) != result.revision:
                raise CatalogError("revision_conflict")
            offset = int(match[2])
            if offset >= len(result.models):
                raise CatalogError("invalid_request")
        page = result.models[offset:offset + int(limit_text)]
        next_offset = offset + len(page)
        return {"revision": result.revision, "models": [item.model_dump(mode="json") for item in page],
                "nextCursor": f"{result.revision}:{next_offset}" if next_offset < len(result.models) else None}
    except CatalogError as error:
        return error_response(error)


@router.post("/api/providers/{provider_id}/models", status_code=201, operation_id="createProviderModel")
async def create_custom_model(provider_id: str, request: Request):
    try:
        payload = await mutation_body(request, ProviderModelRequest)
        try:
            model = CustomModel(key=str(uuid4()), model_id=payload.modelId, name=payload.name,
                context_limit=payload.contextLimit, output_limit=payload.outputLimit,
                tools=payload.tools, source="manual")
        except ValueError:
            raise CatalogError("invalid_request") from None
        result = await asyncio.to_thread(service(request).save_model, provider_id, model,
            expected_revision=payload.expectedRevision)
        return JSONResponse(status_code=201, content={"revision": result.revision,
            "models": [item.model_dump(mode="json") for item in result.models]})
    except CatalogError as error:
        return error_response(error)


@router.post("/api/providers/{provider_id}/models/refresh", operation_id="refreshProviderModels")
async def refresh_custom_models(provider_id: str, request: Request):
    from opensprite_backend.providers.catalog_models import ProviderEndpointSnapshot
    from opensprite_backend.providers.custom_discovery import discover_models
    try:
        payload = await mutation_body(request, ProviderRevisionRequest)
        manager = mutations(request)
        provider, secret = await manager.discovery_credentials(provider_id, expected_revision=payload.expectedRevision)
        client = getattr(request.app.state, "provider_http_client", None)
        if client is None:
            raise CatalogError()
        endpoint = ProviderEndpointSnapshot(provider.id, provider.revision, provider.protocol, provider.base_url, provider.auth_mode)
        try:
            ids = await discover_models(client, endpoint, secret)
        finally:
            secret = None
        result = await manager.merge_discovery(provider_id, ids, expected_revision=payload.expectedRevision)
        return {"revision": result.revision, "models": [item.model_dump(mode="json") for item in result.models]}
    except CatalogError as error:
        return error_response(error)
