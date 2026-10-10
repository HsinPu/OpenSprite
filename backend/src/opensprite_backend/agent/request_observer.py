"""Optional, synchronous notifications; execution never waits for diagnostics."""
from datetime import datetime
from typing import Protocol

from opensprite_backend.inference.models import ModelRequest


class ModelRequestObserver(Protocol):
    def record_request(self, *, run_id: str, request_sequence: int,
                       request: ModelRequest, created_at: datetime) -> None: ...
