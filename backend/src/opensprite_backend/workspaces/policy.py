"""Canonical root validation for user-selected workspaces."""

from __future__ import annotations

from dataclasses import dataclass
import os
import stat
from pathlib import Path

from .models import WorkspaceAvailability, WorkspaceUnavailableReason


class UnsafeWorkspaceRoot(ValueError):
    """Raised without embedding a user-controlled path."""


class InvalidWorkspaceRoot(ValueError):
    """Raised when a requested root is not a usable directory."""


@dataclass(frozen=True, slots=True)
class WorkspaceRootStatus:
    availability: WorkspaceAvailability
    unavailable_reason: WorkspaceUnavailableReason | None


class WorkspaceRootPolicy:
    def __init__(
        self,
        *,
        data_root: Path,
        user_home: Path,
        install_root: Path | None = None,
    ) -> None:
        self._data_root = data_root.resolve(strict=False)
        self._install_root = (
            None if install_root is None else install_root.resolve(strict=False)
        )
        self._user_home = user_home.resolve(strict=False)

    def validate_new_root(self, value: str) -> str:
        path = self._parse_absolute(value)
        try:
            if (
                path.is_symlink()
                or self._is_junction(path)
                or self._is_reparse_point(path)
            ):
                raise UnsafeWorkspaceRoot
            resolved = path.resolve(strict=True)
        except UnsafeWorkspaceRoot:
            raise
        except (OSError, RuntimeError):
            raise InvalidWorkspaceRoot from None
        if not resolved.is_dir():
            raise InvalidWorkspaceRoot
        if self._is_unsafe(resolved):
            raise UnsafeWorkspaceRoot
        if not os.access(resolved, os.R_OK | os.X_OK):
            raise InvalidWorkspaceRoot
        return str(resolved)

    def inspect_saved_root(self, value: str) -> WorkspaceRootStatus:
        try:
            path = self._parse_absolute(value)
        except InvalidWorkspaceRoot:
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.UNSAFE,
            )
        try:
            if (
                path.is_symlink()
                or self._is_junction(path)
                or self._is_reparse_point(path)
            ):
                return WorkspaceRootStatus(
                    WorkspaceAvailability.UNAVAILABLE,
                    WorkspaceUnavailableReason.UNSAFE,
                )
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.MISSING,
            )
        except PermissionError:
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.ACCESS_DENIED,
            )
        except (OSError, RuntimeError):
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.MISSING,
            )
        if not resolved.is_dir():
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.NOT_DIRECTORY,
            )
        if self._is_unsafe(resolved):
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.UNSAFE,
            )
        if not os.access(resolved, os.R_OK | os.X_OK):
            return WorkspaceRootStatus(
                WorkspaceAvailability.UNAVAILABLE,
                WorkspaceUnavailableReason.ACCESS_DENIED,
            )
        return WorkspaceRootStatus(WorkspaceAvailability.AVAILABLE, None)

    @staticmethod
    def comparison_key(value: str) -> str:
        return os.path.normcase(os.path.normpath(value))

    @staticmethod
    def _parse_absolute(value: str) -> Path:
        if (
            type(value) is not str
            or not value
            or len(value) > 32_768
            or any(character in value for character in ("\x00", "\r", "\n"))
        ):
            raise InvalidWorkspaceRoot
        path = Path(value)
        if not path.is_absolute():
            raise InvalidWorkspaceRoot
        return path

    @staticmethod
    def _is_junction(path: Path) -> bool:
        checker = getattr(path, "is_junction", None)
        return bool(checker is not None and checker())

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        if os.name != "nt":
            return False
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(attributes & reparse_flag)

    def _is_unsafe(self, path: Path) -> bool:
        if path.parent == path or self._same(path, self._user_home):
            return True
        if self._within(path, self._data_root):
            return True
        return self._install_root is not None and self._within(path, self._install_root)

    @classmethod
    def _same(cls, left: Path, right: Path) -> bool:
        return cls.comparison_key(str(left)) == cls.comparison_key(str(right))

    @classmethod
    def _within(cls, child: Path, parent: Path) -> bool:
        child_key = cls.comparison_key(str(child))
        parent_key = cls.comparison_key(str(parent))
        if child_key == parent_key:
            return True
        try:
            return parent_key in {
                cls.comparison_key(str(candidate)) for candidate in child.parents
            }
        except (OSError, RuntimeError):
            return False
