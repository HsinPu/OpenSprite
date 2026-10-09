"""Official policies loaded as an ordinary API v5 wheel."""
from dataclasses import dataclass
from .loop import StandardLoop

@dataclass(frozen=True)
class LoopFactory:
    recovery: bool = True
    api_version = 5
    def create(self):
        return StandardLoop(self.recovery)

def standard():
    return LoopFactory()

def no_recovery():
    return LoopFactory(False)
