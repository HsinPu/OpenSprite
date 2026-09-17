"""Translate a frozen response-mode decision into a provider parameter."""
from __future__ import annotations
import re
from .gateway import ModelGatewayError
from .models import InferenceFailure, ModelRequest
from .capabilities import fixed_model_capability
from opensprite_backend.response_modes import LEGACY_RESPONSE_MODES, resolve_response_mode


def request_effort(request: ModelRequest) -> str | None:
    if request.reasoning_resolution is not None:
        return request.reasoning_resolution.effective
    if request.response_mode == "default":
        return None
    # Legacy transcripts and internal callers retain their original interpretation.
    if request.response_mode in LEGACY_RESPONSE_MODES:
        if request.provider_id == "openai" and re.match(r"^(?:gpt-[5-9]|o[1-9])", request.model_id, re.I) is None:
            raise invalid_response()
        return LEGACY_RESPONSE_MODES[request.response_mode]
    capability = fixed_model_capability(request.provider_id, request.model_id)
    return resolve_response_mode(request.response_mode, capability.reasoning_efforts if capability else None).effective


def invalid_response() -> ModelGatewayError:
    return ModelGatewayError(InferenceFailure.INVALID_PROVIDER_RESPONSE)
