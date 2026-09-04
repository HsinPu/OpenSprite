"""Authenticated schedule management HTTP routes."""

from __future__ import annotations

import json
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse

from opensprite_backend.schedules.repository import (
    ScheduleFailure,
    ScheduleStoreError,
)
from opensprite_backend.schedules.runtime_status import (
    detect_schedule_runtime_status,
)
from opensprite_backend.schedules.service import ScheduleOperations

from .schedule_models import (
    CreateScheduleRequest,
    OccurrenceListResponse,
    OccurrenceResponse,
    RevisionRequest,
    RuntimeStatusResponse,
    ScheduleErrorDetail,
    ScheduleErrorEnvelope,
    ScheduleListResponse,
    ScheduleResponse,
    UpdateScheduleRequest,
    occurrence_list_response,
    occurrence_response,
    schedule_list_response,
    schedule_response,
)


router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _schedules(request: Request) -> ScheduleOperations:
    return cast(ScheduleOperations, request.app.state.schedules)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


async def strict_json(request: Request) -> None:
    body = await request.body()
    try:
        json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST) from None


def schedule_error_response(failure: ScheduleFailure) -> JSONResponse:
    code, message, retryable = {
        ScheduleFailure.INVALID_REQUEST: (400, "排程資料無效。", False),
        ScheduleFailure.NOT_FOUND: (404, "找不到指定的排程。", False),
        ScheduleFailure.REVISION_CONFLICT: (409, "排程已在其他頁面更新。", True),
        ScheduleFailure.DATABASE_UNAVAILABLE: (503, "排程資料暫時無法使用。", True),
        ScheduleFailure.WORKSPACE_NOT_FOUND: (404, "找不到指定的工作區。", False),
        ScheduleFailure.WORKSPACE_STORE_UNAVAILABLE: (503, "工作區設定暫時無法使用。", True),
        ScheduleFailure.WORKSPACE_BUSY: (409, "工作區或排程目前仍在執行。", True),
    }[failure]
    body = ScheduleErrorEnvelope(
        error=ScheduleErrorDetail(
            code=failure.value,
            message=message,
            retryable=retryable,
        )
    )
    return JSONResponse(status_code=code, content=body.model_dump(mode="json"))


@router.get("", operation_id="listSchedules", response_model=ScheduleListResponse)
async def list_schedules(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    schedules: ScheduleOperations = Depends(_schedules),
) -> ScheduleListResponse:
    page = await schedules.list(limit=limit, before=before)
    latest = await schedules.latest_occurrences(tuple(item.id for item in page.items))
    return schedule_list_response(page, latest)


@router.post(
    "",
    operation_id="createSchedule",
    status_code=status.HTTP_201_CREATED,
    response_model=ScheduleResponse,
    dependencies=[Depends(strict_json)],
)
async def create_schedule(
    payload: CreateScheduleRequest,
    schedules: ScheduleOperations = Depends(_schedules),
) -> ScheduleResponse:
    return schedule_response(await schedules.create(payload.draft()))


@router.get(
    "/runtime-status",
    operation_id="getScheduleRuntimeStatus",
    response_model=RuntimeStatusResponse,
)
async def runtime_status() -> RuntimeStatusResponse:
    current = detect_schedule_runtime_status()
    return RuntimeStatusResponse(
        platform=current.platform,
        continuity=current.continuity,
    )


@router.get(
    "/{schedule_id}",
    operation_id="getSchedule",
    response_model=ScheduleResponse,
)
async def get_schedule(
    schedule_id: UUID,
    schedules: ScheduleOperations = Depends(_schedules),
) -> ScheduleResponse:
    item = await schedules.get(str(schedule_id))
    latest = await schedules.latest_occurrences((item.id,))
    return schedule_response(item, latest.get(item.id))


@router.put(
    "/{schedule_id}",
    operation_id="updateSchedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(strict_json)],
)
async def update_schedule(
    schedule_id: UUID,
    payload: UpdateScheduleRequest,
    schedules: ScheduleOperations = Depends(_schedules),
) -> ScheduleResponse:
    return schedule_response(
        await schedules.update(str(schedule_id), payload.revision, payload.draft())
    )


@router.delete(
    "/{schedule_id}",
    operation_id="deleteSchedule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule(
    schedule_id: UUID,
    request: Request,
    schedules: ScheduleOperations = Depends(_schedules),
) -> Response:
    if await request.body():
        raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
    await schedules.delete(str(schedule_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _revision_action(
    schedule_id: UUID,
    payload: RevisionRequest,
    schedules: ScheduleOperations,
    action: str,
) -> ScheduleResponse:
    method = schedules.pause if action == "pause" else schedules.resume
    return schedule_response(await method(str(schedule_id), payload.revision))


@router.post(
    "/{schedule_id}/pause",
    operation_id="pauseSchedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(strict_json)],
)
async def pause_schedule(
    schedule_id: UUID,
    payload: RevisionRequest,
    schedules: ScheduleOperations = Depends(_schedules),
) -> ScheduleResponse:
    return await _revision_action(schedule_id, payload, schedules, "pause")


@router.post(
    "/{schedule_id}/resume",
    operation_id="resumeSchedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(strict_json)],
)
async def resume_schedule(
    schedule_id: UUID,
    payload: RevisionRequest,
    schedules: ScheduleOperations = Depends(_schedules),
) -> ScheduleResponse:
    return await _revision_action(schedule_id, payload, schedules, "resume")


@router.post(
    "/{schedule_id}/run-now",
    operation_id="runScheduleNow",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=OccurrenceResponse,
)
async def run_schedule_now(
    schedule_id: UUID,
    request: Request,
    schedules: ScheduleOperations = Depends(_schedules),
) -> OccurrenceResponse:
    if await request.body():
        raise ScheduleStoreError(ScheduleFailure.INVALID_REQUEST)
    return occurrence_response(await schedules.run_now(str(schedule_id)))


@router.get(
    "/{schedule_id}/occurrences",
    operation_id="listScheduleOccurrences",
    response_model=OccurrenceListResponse,
)
async def list_occurrences(
    schedule_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    schedules: ScheduleOperations = Depends(_schedules),
) -> OccurrenceListResponse:
    return occurrence_list_response(
        await schedules.occurrences(
            str(schedule_id),
            limit=limit,
            before=before,
        )
    )
