"""Core-issued terminal execution errors; Loops use typed operation results."""
from opensprite_backend.conversations.models import PublicRunError


class ExecutionFailed(Exception):
    def __init__(self, error: PublicRunError):
        super().__init__(error.code)
        self.error = error


class RunCancelled(Exception):
    pass
