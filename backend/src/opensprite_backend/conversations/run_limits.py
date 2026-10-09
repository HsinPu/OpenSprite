"""Persisted evidence of a core limit, independent of the plugin SDK."""
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Literal

LimitKind = Literal["duration_seconds", "model_requests", "summary_requests", "generated_chars", "host_operations"]
LIMIT_ERROR_CODES = {
    "duration_seconds": "run_deadline_exceeded",
    "model_requests": "model_request_limit_reached",
    "summary_requests": "summary_request_limit_reached",
    "generated_chars": "generated_text_limit_reached",
    "host_operations": "host_operation_limit_reached",
}


def valid_limit_data(value: object, error_code: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != {"kind", "maximum", "used"}:
        return False
    kind = value["kind"]
    if not isinstance(kind, str) or kind not in LIMIT_ERROR_CODES or LIMIT_ERROR_CODES[kind] != error_code:
        return False
    numbers = (value["maximum"], value["used"])
    if any(type(n) not in (int, float) or not isfinite(n) or not 0 <= n <= 2**53 - 1 for n in numbers):
        return False
    return value["maximum"] > 0 and (kind == "duration_seconds" or all(type(n) is int for n in numbers))


@dataclass(frozen=True, slots=True)
class RunLimitEvidence:
    kind: LimitKind
    maximum: int | float
    used: int | float

    def as_data(self) -> dict[str, object]:
        data = {"kind": self.kind, "maximum": self.maximum, "used": self.used}
        if not valid_limit_data(data, LIMIT_ERROR_CODES.get(self.kind)):
            raise ValueError("invalid limit evidence")
        return data
