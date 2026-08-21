"""Provider-neutral model request and streaming boundary."""

from .gateway import ModelGateway, ModelGatewayError
from .native_gateway import NativeModelGateway
from .models import (
    InferenceFailure,
    ModelCompleted,
    ModelFinishReason,
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)

__all__ = [
    "InferenceFailure",
    "ModelCompleted",
    "ModelFinishReason",
    "ModelGateway",
    "ModelGatewayError",
    "ModelMessage",
    "NativeModelGateway",
    "ModelRequest",
    "ModelStreamEvent",
    "ModelTextDelta",
    "ModelToolCall",
    "ModelToolDefinition",
    "ModelUsage",
]
