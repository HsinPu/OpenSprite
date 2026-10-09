"""Core-issued terminal execution errors; Loops use typed operation results."""
from opensprite_backend.conversations.models import PublicRunError
from opensprite_backend.conversations.run_limits import RunLimitEvidence


class ExecutionFailed(Exception):
    def __init__(self, error: PublicRunError, *, limit: RunLimitEvidence | None = None):
        super().__init__(error.code)
        self.error = error
        self.limit = limit


class RunCancelled(Exception):
    pass
