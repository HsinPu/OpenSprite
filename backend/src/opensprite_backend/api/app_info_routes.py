"""Read-only application build identity route."""

from typing import cast

from fastapi import APIRouter, Request

from opensprite_backend.models import AppInfo

router = APIRouter()


@router.get(
    "/api/app-info",
    operation_id="getAppInfo",
    response_model=AppInfo,
    tags=["app-info"],
)
async def get_app_info(request: Request) -> AppInfo:
    return cast(AppInfo, request.app.state.app_info)
