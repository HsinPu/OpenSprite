"""Central dated, bounded, secret-safe runtime logging."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import os
from pathlib import Path
import re
from typing import Callable

from .app_paths import AppPaths

_REDACTIONS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:x-api-key|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _redact(value: str) -> str:
    result = value
    for pattern in _REDACTIONS:
        result = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", result)
    return result


class DatedRuntimeHandler(logging.Handler):
    def __init__(self, root: Path, *, clock: Callable[[], datetime] | None = None, max_bytes: int = 10 * 1024 * 1024, backups: int = 2, retention_days: int = 14) -> None:
        super().__init__(logging.INFO)
        self._root = root
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._max_bytes = max_bytes
        self._backups = backups
        self._retention_days = retention_days
        self._cleaned_date: date | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            now = self._clock()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("logging clock must be timezone-aware")
            dated = self._root / now.date().isoformat()
            dated.mkdir(parents=True, exist_ok=True, mode=0o700)
            if os.name != "nt": dated.chmod(0o700)
            if self._cleaned_date != now.date():
                self._cleanup(now.date())
                self._cleaned_date = now.date()
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            line = _redact(f"{now.isoformat(timespec='milliseconds')} {record.levelname} {record.name} {message}\n")
            encoded = line.encode("utf-8")
            target = dated / "backend.log"
            if target.exists() and target.stat().st_size + len(encoded) > self._max_bytes:
                self._rotate(dated)
            with target.open("ab") as stream:
                stream.write(encoded)
                stream.flush()
            if os.name != "nt": target.chmod(0o600)
        except Exception:
            self.handleError(record)

    def _rotate(self, dated: Path) -> None:
        oldest = dated / f"backend.{self._backups}.log"
        oldest.unlink(missing_ok=True)
        for index in range(self._backups - 1, 0, -1):
            source = dated / f"backend.{index}.log"
            if source.exists(): source.replace(dated / f"backend.{index + 1}.log")
        active = dated / "backend.log"
        if active.exists(): active.replace(dated / "backend.1.log")

    def _cleanup(self, today: date) -> None:
        if not self._root.exists(): return
        cutoff = today - timedelta(days=self._retention_days)
        root = self._root.resolve(strict=False)
        for child in self._root.iterdir():
            if not child.is_dir() or child.is_symlink(): continue
            try: child_date = date.fromisoformat(child.name)
            except ValueError: continue
            if child_date >= cutoff: continue
            resolved = child.resolve(strict=False)
            if resolved.parent != root: continue
            for item in child.iterdir():
                if item.is_file() and not item.is_symlink(): item.unlink()
            try: child.rmdir()
            except OSError: continue


class RuntimeLoggingSession:
    def __init__(self, handler: DatedRuntimeHandler) -> None:
        self._handler = handler
        self._loggers = (logging.getLogger("opensprite"), logging.getLogger("uvicorn.error"))
        for logger in self._loggers:
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)

    def close(self) -> None:
        for logger in self._loggers:
            logger.removeHandler(self._handler)
        self._handler.close()


def configure_runtime_logging(paths: AppPaths) -> RuntimeLoggingSession:
    return RuntimeLoggingSession(DatedRuntimeHandler(paths.backend_logs_dir))
