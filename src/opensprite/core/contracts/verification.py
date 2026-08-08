"""Pure contracts for interpreting verification tool results."""

from typing import Any

from .tool_results import classify_tool_result_status


def classify_verification_result(result: str) -> dict[str, Any]:
    """Classify one verification result string into structured outcome fields."""
    text = str(result or "").strip()
    if text.lstrip().startswith("{"):
        status = classify_tool_result_status(text)
        if not status.ok and status.error:
            if status.category == "python_compile_failed":
                return {"status": "failed", "ok": False, "attempted": True, "name": "python_compile"}
            if status.category == "verification_timed_out":
                first_error_line = status.error.splitlines()[0].strip()
                name = first_error_line.removeprefix("Verification timed out:").strip() or None
                return {"status": "timed_out", "ok": False, "attempted": True, "name": name}
            if status.category == "verification_failed":
                first_error_line = status.error.splitlines()[0].strip()
                name = first_error_line.removeprefix("Verification failed:").strip() or None
                return {"status": "failed", "ok": False, "attempted": True, "name": name}
            return {"status": "error", "ok": False, "attempted": True, "name": None}

    first_line = text.splitlines()[0].strip() if text else ""
    for prefix, status, ok in (
        ("Verification passed: ", "passed", True),
        ("Verification skipped: ", "skipped", False),
    ):
        if first_line.startswith(prefix):
            return {
                "status": status,
                "ok": ok,
                "attempted": True,
                "name": first_line[len(prefix):].strip() or None,
            }
    return {"status": "unknown", "ok": False, "attempted": bool(text), "name": None}
