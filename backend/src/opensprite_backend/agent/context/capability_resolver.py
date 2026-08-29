"""Resolve one selected model to a backend-trusted capability."""

from __future__ import annotations

from typing import Protocol

from opensprite_backend.inference.capabilities import (
    ModelCapability,
)
from opensprite_backend.inference.models import InferenceFailure
from opensprite_backend.models import ProviderId


class ModelCapabilityNotFound(Exception):
    pass


class ModelCapabilityProviderError(Exception):
    def __init__(self, failure: InferenceFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


class ModelCapabilityResolver(Protocol):
    async def resolve(
        self,
        provider_id: ProviderId,
        model_id: str,
    ) -> ModelCapability: ...
