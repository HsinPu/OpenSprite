"""Protocol implemented by the explicitly composed native Provider gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from .models import InferenceFailure, ModelRequest, ModelStreamEvent


class ModelGatewayError(Exception):
    """Typed Provider failure whose string never contains upstream detail."""

    def __init__(self, failure: InferenceFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


class ModelGateway(Protocol):
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...


class ProviderInferenceAdapter(Protocol):
    def stream(
        self,
        request: ModelRequest,
        api_key: str,
    ) -> AsyncIterator[ModelStreamEvent]: ...
