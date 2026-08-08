import pytest

from opensprite.core.contracts.tool_results import tool_error_result
from opensprite.core.contracts.verification import classify_verification_result


@pytest.mark.parametrize(
    ("result", "expected"),
    (
        (
            "Verification passed: pytest\n1 passed",
            {"status": "passed", "ok": True, "attempted": True, "name": "pytest"},
        ),
        (
            "Verification skipped: web_build",
            {"status": "skipped", "ok": False, "attempted": True, "name": "web_build"},
        ),
        (
            "",
            {"status": "unknown", "ok": False, "attempted": False, "name": None},
        ),
        (
            "unexpected output",
            {"status": "unknown", "ok": False, "attempted": True, "name": None},
        ),
    ),
)
def test_classify_verification_text_results(result, expected):
    assert classify_verification_result(result) == expected


@pytest.mark.parametrize(
    ("category", "error", "expected"),
    (
        (
            "python_compile_failed",
            "Python compile verification failed",
            {"status": "failed", "ok": False, "attempted": True, "name": "python_compile"},
        ),
        (
            "verification_failed",
            "Verification failed: pytest\n1 failed",
            {"status": "failed", "ok": False, "attempted": True, "name": "pytest"},
        ),
        (
            "verification_timed_out",
            "Verification timed out: web_build\nCommand timed out",
            {"status": "timed_out", "ok": False, "attempted": True, "name": "web_build"},
        ),
        (
            "invalid_arguments",
            "Unknown verification action",
            {"status": "error", "ok": False, "attempted": True, "name": None},
        ),
    ),
)
def test_classify_structured_verification_errors(category, error, expected):
    result = tool_error_result(
        error,
        error_type="VerifyToolError",
        category=category,
    )

    assert classify_verification_result(result) == expected
