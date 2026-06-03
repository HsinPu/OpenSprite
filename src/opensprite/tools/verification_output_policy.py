"""Shared parsing policy for verifier command output."""

from __future__ import annotations


PYTEST_NO_TESTS_MARKERS = (
    "collected 0 items",
    "no tests ran",
)


def pytest_collected_no_tests(output: str | None) -> bool:
    normalized = str(output or "").lower()
    return any(marker in normalized for marker in PYTEST_NO_TESTS_MARKERS)
