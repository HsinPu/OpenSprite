"""Capability-aware translation from OpenSprite response modes."""

from __future__ import annotations

import re

from .gateway import ModelGatewayError
from .models import InferenceFailure


_EFFORT = {"fast": "low", "balanced": "medium", "deep": "high"}
_OPENAI_REASONING_MODEL = re.compile(r"^(?:gpt-[5-9]|o[1-9])", re.IGNORECASE)


def effort(response_mode: str) -> str | None:
    if response_mode == "default":
        return None
    try:
        return _EFFORT[response_mode]
    except KeyError as error:
        raise invalid_response() from error


def openai_effort(model_id: str, response_mode: str) -> str | None:
    value = effort(response_mode)
    if value is not None and _OPENAI_REASONING_MODEL.match(model_id) is None:
        raise invalid_response()
    return value


def invalid_response() -> ModelGatewayError:
    return ModelGatewayError(InferenceFailure.INVALID_PROVIDER_RESPONSE)
