from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path

from opensprite_backend.runtime_logging import DatedRuntimeHandler


def record(message: str, *, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord("opensprite.test", logging.ERROR if exc_info else logging.INFO, __file__, 1, message, (), exc_info)


def test_handler_writes_dated_redacted_log_and_traceback(tmp_path: Path) -> None:
    handler = DatedRuntimeHandler(tmp_path, clock=lambda: datetime(2026, 8, 31, 13, 20, tzinfo=timezone.utc))
    handler.emit(record("Authorization: Bearer secret-token apiKey=secret-value sk-1234567890"))
    try:
        raise RuntimeError("failed with sk-abcdefghij")
    except RuntimeError:
        import sys
        handler.emit(record("request failed", exc_info=sys.exc_info()))
    content = (tmp_path / "2026-08-31" / "backend.log").read_text(encoding="utf-8")
    for secret in ("secret-token", "secret-value", "sk-1234567890", "sk-abcdefghij"):
        assert secret not in content
    assert "[REDACTED]" in content and "Traceback" in content


def test_handler_rotates_by_size_and_changes_date(tmp_path: Path) -> None:
    values = iter([datetime(2026, 8, 30, 23, 59, tzinfo=timezone.utc), datetime(2026, 8, 30, 23, 59, tzinfo=timezone.utc), datetime(2026, 8, 31, 0, 1, tzinfo=timezone.utc)])
    handler = DatedRuntimeHandler(tmp_path, clock=lambda: next(values), max_bytes=80)
    handler.emit(record("first message that fills the file"))
    handler.emit(record("second message rotates the file"))
    handler.emit(record("new day"))
    assert (tmp_path / "2026-08-30" / "backend.1.log").is_file()
    assert (tmp_path / "2026-08-30" / "backend.log").is_file()
    assert (tmp_path / "2026-08-31" / "backend.log").is_file()


def test_handler_removes_only_expired_date_directories(tmp_path: Path) -> None:
    for name in ("2026-08-01", "2026-08-20", "keep-me"):
        directory = tmp_path / name; directory.mkdir(parents=True); (directory / "backend.log").write_text("old", encoding="utf-8")
    DatedRuntimeHandler(tmp_path, clock=lambda: datetime(2026, 8, 31, tzinfo=timezone.utc)).emit(record("cleanup"))
    assert not (tmp_path / "2026-08-01").exists()
    assert (tmp_path / "2026-08-20").exists()
    assert (tmp_path / "keep-me").exists()
