"""Response preferences and the immutable reasoning decision used for a Run."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class ResponseMode(StrEnum):
    DEFAULT = "default"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"
    ULTRA = "ultra"


ResponseModeValue = Literal["default", "low", "medium", "high", "xhigh", "max", "ultra"]
HistoricalResponseMode = Literal["default", "fast", "balanced", "deep", "low", "medium", "high", "xhigh", "max", "ultra"]
RESPONSE_MODES = tuple(mode.value for mode in ResponseMode)
LEGACY_RESPONSE_MODES = {"fast": "low", "balanced": "medium", "deep": "high"}
HISTORICAL_RESPONSE_MODES = (*LEGACY_RESPONSE_MODES, *RESPONSE_MODES)
NATIVE_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def migrate_response_mode(value: object) -> str:
    """Storage migrations preserve default and translate retired preference names."""
    if not isinstance(value, str) or value not in HISTORICAL_RESPONSE_MODES:
        raise ValueError("invalid response mode")
    return LEGACY_RESPONSE_MODES.get(value, value)


@dataclass(frozen=True, slots=True)
class ReasoningResolution:
    requested: HistoricalResponseMode
    effective: str | None
    status: Literal["exact", "fallback", "provider_default", "unknown"]

    def __post_init__(self) -> None:
        if self.requested not in HISTORICAL_RESPONSE_MODES:
            raise ValueError("invalid requested response mode")
        if self.status in {"exact", "fallback"}:
            if self.effective not in NATIVE_EFFORTS:
                raise ValueError("invalid effective reasoning effort")
        elif self.status not in {"provider_default", "unknown"} or self.effective is not None:
            raise ValueError("invalid reasoning resolution")


def resolve_response_mode(mode: HistoricalResponseMode, supported: tuple[str, ...] | None) -> ReasoningResolution:
    if mode == "default":
        return ReasoningResolution(mode, None, "provider_default")
    requested = migrate_response_mode(mode)
    if supported is None:
        return ReasoningResolution(mode, None, "unknown")
    available = tuple(value for value in NATIVE_EFFORTS if value in supported)
    if not available:
        return ReasoningResolution(mode, None, "provider_default")
    if requested in available:
        return ReasoningResolution(mode, requested, "exact")
    return ReasoningResolution(mode, available[-1], "fallback")
