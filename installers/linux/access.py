"""Installer-only Linux access policy and TTY bootstrap helper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import secrets
import sys
from typing import TextIO

from opensprite_backend.authentication import AccessMode, AccessPolicy, JsonAccessPolicyStore
from opensprite_backend.authentication.store import BootstrapRecord, JsonAccessStore, JsonBootstrapStore
from opensprite_backend.app_paths import build_app_paths


def set_access_mode(root: Path, mode: AccessMode) -> None:
    paths = build_app_paths(root)
    JsonAccessPolicyStore(paths.access_policy_file).set(AccessPolicy(mode))
    if mode is AccessMode.TRUSTED_LOCAL:
        JsonBootstrapStore(paths.access_bootstrap_file).delete()
    _protect(paths.config_dir, paths.access_policy_file)


def issue_bootstrap(root: Path, port: int, reset: bool, tty: TextIO) -> bool:
    paths = build_app_paths(root)
    access = JsonAccessStore(paths.access_file)
    if access.get() is not None and not reset:
        return False
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    bootstrap = JsonBootstrapStore(paths.access_bootstrap_file)
    bootstrap.set(BootstrapRecord(hashlib.sha256(token.encode("ascii")).hexdigest(), now, now + timedelta(minutes=30)))
    if reset:
        access.delete()
    _protect(paths.state_dir, paths.access_bootstrap_file)
    tty.write("\nOpenSprite one-time setup URL (expires in 30 minutes):\n")
    tty.write(f"http://localhost:{port}/#setup={token}\n\n")
    tty.flush()
    return True


def _protect(directory: Path, file: Path) -> None:
    home = directory.parent
    if home.exists():
        home.chmod(0o700)
    if directory.exists():
        directory.chmod(0o700)
    if file.exists():
        file.chmod(0o600)


def _main() -> int:
    if len(sys.argv) not in {4, 5}:
        raise SystemExit("Invalid installer access-helper invocation.")
    operation, root_text, value = sys.argv[1:4]
    root = Path(root_text).expanduser().resolve(strict=False)
    if operation == "policy" and len(sys.argv) == 4:
        set_access_mode(root, AccessMode(value))
        return 0
    if operation == "bootstrap" and len(sys.argv) == 5:
        port = int(value)
        reset = sys.argv[4] == "reset"
        if sys.argv[4] not in {"keep", "reset"} or not 1024 <= port <= 65535:
            raise SystemExit("Invalid installer bootstrap invocation.")
        with open("/dev/tty", "w", encoding="utf-8", buffering=1) as tty:
            issue_bootstrap(root, port, reset, tty)
        return 0
    raise SystemExit("Invalid installer access-helper invocation.")


if __name__ == "__main__":
    raise SystemExit(_main())
