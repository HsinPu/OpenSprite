"""Authenticated execution-plugin package cache and bundle HTTP boundary."""

import asyncio
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from opensprite_backend.execution_plugins.models import ExecutionPackageError, PackageListResponse
from .execution_package_upload import read_wheel_upload

router = APIRouter(prefix="/api/execution-plugin-packages", tags=["execution-plugin-packages"])

_ERRORS = {
    "invalid_request": (400, "Request validation failed.", False),
    "invalid_package": (400, "The wheel format or execution-plugin metadata is unsupported.", False),
    "incompatible_package": (400, "The wheel is incompatible with this Python, backend or installed dependency environment.", False),
    "package_too_large": (413, "The wheel or imported package limit was exceeded.", False),
    "package_not_found": (404, "The imported package was not found.", False),
    "packages_store_unavailable": (503, "Imported execution-plugin packages are unavailable.", True),
    "deployment_unavailable": (503, "Docker deployment requires a valid operator-configured base image.", True),
    "internal_error": (500, "An internal error occurred.", False),
}


async def execution_package_error_handler(request: Request, error: ExecutionPackageError):
    del request
    code = error.code if error.code in _ERRORS else "internal_error"
    status, message, retryable = _ERRORS[code]
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "retryable": retryable}})


def _service(request):
    service = getattr(request.app.state, "execution_packages", None)
    if service is None:
        raise ExecutionPackageError("packages_store_unavailable")
    if request.query_params:
        raise ExecutionPackageError("invalid_request")
    return service


async def _mutation(operation, *arguments):
    task = asyncio.create_task(asyncio.to_thread(operation, *arguments))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


@router.get("", operation_id="listExecutionPluginPackages", response_model=PackageListResponse)
async def list_execution_packages(request: Request):
    return await asyncio.to_thread(_service(request).list)


@router.post("", operation_id="importExecutionPluginPackage", response_model=PackageListResponse,
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}},
        "additionalProperties": False}}}}})
async def import_execution_package(request: Request):
    service = _service(request)
    file_name, data = await read_wheel_upload(request)
    return await _mutation(service.import_wheel, file_name, data)


@router.delete("/{package_id}", operation_id="deleteExecutionPluginPackage", status_code=204)
async def delete_execution_package(package_id: str, request: Request):
    await _mutation(_service(request).delete, package_id)
    return Response(status_code=204)


@router.get("/{package_id}/deployment-bundle", operation_id="getExecutionPluginDeploymentBundle")
async def get_execution_package_bundle(package_id: str, request: Request):
    data = await asyncio.to_thread(_service(request).bundle, package_id)
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="opensprite-execution-plugin-deployment.zip"',
                             "Cache-Control": "no-store"})
