"""Portable checks for the Linux access helper and installer contract."""

from __future__ import annotations

import importlib.util
from io import StringIO
import json
from pathlib import Path

from opensprite_backend.authentication import AccessMode


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "installers" / "linux" / "access.py"
INSTALLER = ROOT / "installers" / "linux" / "install.sh"


def load_helper():
    spec = importlib.util.spec_from_file_location("opensprite_linux_access", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_linux_helper_persists_policy_and_never_stores_raw_bootstrap(tmp_path: Path) -> None:
    helper = load_helper()
    data = tmp_path / ".opensprite"
    helper.set_access_mode(data, AccessMode.TRUSTED_LOCAL)
    assert json.loads((data / "config" / "access-policy.json").read_text(encoding="utf-8")) == {"version": 1, "mode": "trusted_local"}
    terminal = StringIO()
    assert helper.issue_bootstrap(data, 8765, False, terminal)
    token = terminal.getvalue().split("#setup=", 1)[1].strip()
    assert token not in (data / "state" / "access-bootstrap.json").read_text(encoding="utf-8")


def test_linux_reset_preserves_unrelated_user_data(tmp_path: Path) -> None:
    helper = load_helper()
    data = tmp_path / ".opensprite"
    database = data / "data" / "opensprite.db"
    database.parent.mkdir(parents=True)
    database.write_text("keep", encoding="utf-8")
    helper.issue_bootstrap(data, 8765, True, StringIO())
    assert database.read_text(encoding="utf-8") == "keep"


def test_linux_installer_is_loopback_user_service_and_never_echoes_token() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    assert "--host 127.0.0.1" in source
    assert "--host 0.0.0.0" not in source
    assert "systemctl --user" in source
    assert "not root or sudo" in source
    assert "--test-root" in source and "Unsafe test root" in source
    helper = HELPER.read_text(encoding="utf-8")
    assert 'open("/dev/tty"' in helper
    assert "print(token" not in helper
