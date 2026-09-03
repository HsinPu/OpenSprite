#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app"
USER_DATA_ROOT="$HOME/.opensprite"
UNIT_ROOT="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ACCESS_MODE=""
PORT=8765
RESET_ACCESS=0
NO_START=0
SKIP_SERVICE=0
TEST_ROOT=""

while (($#)); do
  case "$1" in
    --source-root) SOURCE_ROOT="$2"; shift 2 ;;
    --test-root) TEST_ROOT="$2"; shift 2 ;;
    --access-mode) ACCESS_MODE="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --reset-local-access) RESET_ACCESS=1; shift ;;
    --no-start) NO_START=1; shift ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

[[ "$(uname -s)" == "Linux" ]] || { echo "OpenSprite Linux installer requires Linux." >&2; exit 1; }
[[ "${EUID:-$(id -u)}" -ne 0 ]] || { echo "Run this installer as the target user, not root or sudo." >&2; exit 1; }
[[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT >= 1024 && PORT <= 65535)) || { echo "Port must be between 1024 and 65535." >&2; exit 2; }
for command in npm uv python3; do command -v "$command" >/dev/null || { echo "Missing prerequisite: $command" >&2; exit 1; }; done

SOURCE_ROOT="$(realpath -e "$SOURCE_ROOT")"
if [[ -n "$TEST_ROOT" ]]; then
  TEST_ROOT="$(realpath -m "$TEST_ROOT")"; TEMP_ROOT="$(realpath -m "${TMPDIR:-/tmp}")"
  [[ "$TEST_ROOT" == "$TEMP_ROOT"/opensprite-installer-test-* ]] || { echo "Unsafe test root." >&2; exit 1; }
  INSTALL_ROOT="$TEST_ROOT/app"; USER_DATA_ROOT="$TEST_ROOT/.opensprite"; UNIT_ROOT="$TEST_ROOT/systemd"; SKIP_SERVICE=1; NO_START=1
fi
INSTALL_ROOT="$(realpath -m "$INSTALL_ROOT")"
USER_DATA_ROOT="$(realpath -m "$USER_DATA_ROOT")"
EXPECTED_DATA_ROOT="$(realpath -m "$HOME/.opensprite")"
case "$SOURCE_ROOT$INSTALL_ROOT$USER_DATA_ROOT$UNIT_ROOT" in *$'\n'*|*$'\r'*|*'"'*) echo "Paths must not contain control characters or quotes." >&2; exit 1;; esac
[[ "$USER_DATA_ROOT" == "$EXPECTED_DATA_ROOT" || -n "$TEST_ROOT" ]] || { echo "User data root must be $EXPECTED_DATA_ROOT" >&2; exit 1; }
[[ ! -L "$INSTALL_ROOT" && ! -L "$USER_DATA_ROOT" ]] || { echo "Install and data roots must not be symbolic links." >&2; exit 1; }
[[ "$INSTALL_ROOT" == */opensprite/app || -n "$TEST_ROOT" ]] || { echo "Unexpected install root." >&2; exit 1; }
[[ -f "$SOURCE_ROOT/backend/pyproject.toml" && -f "$SOURCE_ROOT/frontend/package.json" && -f "$SOURCE_ROOT/installers/linux/access.py" ]] || { echo "Source root is incomplete." >&2; exit 1; }

POLICY_FILE="$USER_DATA_ROOT/config/access-policy.json"
ACCESS_FILE="$USER_DATA_ROOT/config/access.json"
BOOTSTRAP_FILE="$USER_DATA_ROOT/state/access-bootstrap.json"
if [[ -z "$ACCESS_MODE" ]]; then
  if [[ -f "$POLICY_FILE" ]]; then
    ACCESS_MODE="$(python3 - "$POLICY_FILE" <<'PY'
import json, pathlib, sys
value=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if set(value) != {"version","mode"} or value["version"] != 1 or value["mode"] not in {"trusted_local","password_required"}: raise SystemExit(1)
print(value["mode"])
PY
)"
  elif [[ -f "$ACCESS_FILE" || -f "$BOOTSTRAP_FILE" ]]; then ACCESS_MODE="password_required"
  elif [[ -r /dev/tty && -w /dev/tty ]]; then
    suggested="password_required"; [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" && -z "${SSH_CONNECTION:-}" ]] && suggested="trusted_local"
    printf 'Access mode [trusted_local/password_required] (default %s): ' "$suggested" >/dev/tty
    read -r ACCESS_MODE </dev/tty || true; ACCESS_MODE="${ACCESS_MODE:-$suggested}"
  else echo "First install requires --access-mode trusted_local or password_required." >&2; exit 1
  fi
fi
[[ "$ACCESS_MODE" == "trusted_local" || "$ACCESS_MODE" == "password_required" ]] || { echo "Invalid access mode." >&2; exit 2; }
((RESET_ACCESS == 0)) || [[ "$ACCESS_MODE" == "password_required" ]] || { echo "Reset requires password_required mode." >&2; exit 2; }
if [[ "$ACCESS_MODE" == "password_required" && (! -f "$ACCESS_FILE" || "$RESET_ACCESS" -eq 1) && (! -r /dev/tty || ! -w /dev/tty) ]]; then echo "Password setup requires an interactive /dev/tty." >&2; exit 1; fi

PARENT="$(dirname "$INSTALL_ROOT")"; mkdir -p "$PARENT"
STAGING="$PARENT/.app-staging-$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
PREVIOUS="$PARENT/.app-previous-$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
UNIT_FILE="$UNIT_ROOT/opensprite.service"
STATE_BACKUP="$PARENT/.access-state-$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
mkdir -p "$STATE_BACKUP"
POLICY_EXISTED=0; ACCESS_EXISTED=0; BOOTSTRAP_EXISTED=0; UNIT_EXISTED=0
[[ ! -f "$POLICY_FILE" ]] || { cp -p -- "$POLICY_FILE" "$STATE_BACKUP/access-policy.json"; POLICY_EXISTED=1; }
[[ ! -f "$ACCESS_FILE" ]] || { cp -p -- "$ACCESS_FILE" "$STATE_BACKUP/access.json"; ACCESS_EXISTED=1; }
[[ ! -f "$BOOTSTRAP_FILE" ]] || { cp -p -- "$BOOTSTRAP_FILE" "$STATE_BACKUP/access-bootstrap.json"; BOOTSTRAP_EXISTED=1; }
[[ ! -f "$UNIT_FILE" ]] || { cp -p -- "$UNIT_FILE" "$STATE_BACKUP/opensprite.service"; UNIT_EXISTED=1; }
cutover=0
cleanup() { rm -rf -- "$STAGING" "$STATE_BACKUP"; }
rollback() {
  if ((cutover == 1)); then
    rm -rf -- "$INSTALL_ROOT"
    [[ ! -e "$PREVIOUS" ]] || mv -- "$PREVIOUS" "$INSTALL_ROOT"
  fi
  if ((POLICY_EXISTED == 1)); then mkdir -p "$(dirname "$POLICY_FILE")"; cp -p -- "$STATE_BACKUP/access-policy.json" "$POLICY_FILE"; else rm -f -- "$POLICY_FILE"; fi
  if ((ACCESS_EXISTED == 1)); then mkdir -p "$(dirname "$ACCESS_FILE")"; cp -p -- "$STATE_BACKUP/access.json" "$ACCESS_FILE"; else rm -f -- "$ACCESS_FILE"; fi
  if ((BOOTSTRAP_EXISTED == 1)); then mkdir -p "$(dirname "$BOOTSTRAP_FILE")"; cp -p -- "$STATE_BACKUP/access-bootstrap.json" "$BOOTSTRAP_FILE"; else rm -f -- "$BOOTSTRAP_FILE"; fi
  if ((SKIP_SERVICE == 0)); then
    if ((UNIT_EXISTED == 1)); then mkdir -p "$UNIT_ROOT"; cp -p -- "$STATE_BACKUP/opensprite.service" "$UNIT_FILE"; else rm -f -- "$UNIT_FILE"; fi
    systemctl --user daemon-reload || true
    [[ ! -e "$INSTALL_ROOT" ]] || systemctl --user restart opensprite.service || true
  fi
}
trap cleanup EXIT
trap rollback ERR

mkdir -p "$STAGING/backend" "$STAGING/frontend" "$STAGING/installers"
cp -a "$SOURCE_ROOT/backend/src" "$SOURCE_ROOT/backend/pyproject.toml" "$SOURCE_ROOT/backend/uv.lock" "$SOURCE_ROOT/backend/README.md" "$STAGING/backend/"
cp -a "$SOURCE_ROOT/frontend/src" "$SOURCE_ROOT/frontend/package.json" "$SOURCE_ROOT/frontend/package-lock.json" "$SOURCE_ROOT/frontend/index.html" "$SOURCE_ROOT/frontend/tsconfig.json" "$SOURCE_ROOT/frontend/vite.config.ts" "$SOURCE_ROOT/frontend/README.md" "$STAGING/frontend/"
cp -a "$SOURCE_ROOT/installers/linux" "$STAGING/installers/"
npm --prefix "$STAGING/frontend" ci --ignore-scripts
npm --prefix "$STAGING/frontend" run build
rm -rf -- "$STAGING/frontend/node_modules"

if ((SKIP_SERVICE == 0)); then systemctl --user stop opensprite.service 2>/dev/null || true; fi
if [[ -e "$INSTALL_ROOT" ]]; then mv -- "$INSTALL_ROOT" "$PREVIOUS"; fi
cutover=1
mv -- "$STAGING" "$INSTALL_ROOT"
uv sync --project "$INSTALL_ROOT/backend" --no-dev

VERSION="$(python3 - "$SOURCE_ROOT/backend/pyproject.toml" <<'PY'
import pathlib, re, sys
match=re.search(r'^version\s*=\s*"([^"]+)"\s*$', pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"), re.M)
if not match: raise SystemExit(1)
print(match.group(1))
PY
)"
REVISION="unknown"; DIRTY=true
if command -v git >/dev/null && REVISION_VALUE="$(git -C "$SOURCE_ROOT" rev-parse --short=8 HEAD 2>/dev/null)"; then
  REVISION="$REVISION_VALUE"; [[ -z "$(git -C "$SOURCE_ROOT" status --porcelain -- backend/src backend/pyproject.toml backend/uv.lock frontend/src frontend/package.json frontend/package-lock.json installers 2>/dev/null)" ]] && DIRTY=false
fi
python3 - "$INSTALL_ROOT/build-info.json" "$VERSION" "$REVISION" "$DIRTY" <<'PY'
from datetime import UTC, datetime
import json, pathlib, sys
path=pathlib.Path(sys.argv[1]); payload={"version":sys.argv[2],"revision":sys.argv[3],"dirty":sys.argv[4]=="true","installedAt":datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00","Z")}
path.write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8"); path.chmod(0o600)
PY

INSTALLED_PYTHON="$INSTALL_ROOT/backend/.venv/bin/python"
"$INSTALLED_PYTHON" "$INSTALL_ROOT/installers/linux/access.py" policy "$USER_DATA_ROOT" "$ACCESS_MODE"
if ((SKIP_SERVICE == 0)); then
  mkdir -p "$UNIT_ROOT"
  cat >"$UNIT_FILE" <<EOF
[Unit]
Description=OpenSprite local backend
After=network.target

[Service]
Type=simple
WorkingDirectory="$INSTALL_ROOT/backend"
ExecStart="$INSTALL_ROOT/backend/.venv/bin/uvicorn" opensprite_backend.installed_runtime:create_installed_app --factory --host 127.0.0.1 --port $PORT --no-proxy-headers
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable opensprite.service >/dev/null
  if ((NO_START == 0)); then
    systemctl --user restart opensprite.service
    "$INSTALLED_PYTHON" - "$PORT" <<'PY'
import json, sys, time, urllib.request
url=f"http://127.0.0.1:{sys.argv[1]}/healthz"
for _ in range(80):
    try:
        if json.load(urllib.request.urlopen(url, timeout=.5)) == {"status":"ok"}: break
    except Exception: time.sleep(.25)
else: raise SystemExit("OpenSprite health check timed out.")
PY
  fi
fi

if [[ "$ACCESS_MODE" == "password_required" && (! -f "$ACCESS_FILE" || "$RESET_ACCESS" -eq 1) ]]; then
  ((NO_START == 0)) || { echo "Password setup cannot be issued with --no-start." >&2; exit 1; }
  "$INSTALLED_PYTHON" "$INSTALL_ROOT/installers/linux/access.py" bootstrap "$USER_DATA_ROOT" "$PORT" "$([[ "$RESET_ACCESS" -eq 1 ]] && echo reset || echo keep)"
elif [[ "$ACCESS_MODE" == "trusted_local" && "$NO_START" -eq 0 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" && -z "${SSH_CONNECTION:-}" ]] && command -v xdg-open >/dev/null; then
  xdg-open "http://localhost:$PORT/" >/dev/null 2>&1 || true
fi
rm -rf -- "$PREVIOUS"
cutover=0
printf 'OpenSprite installed. mode=%s url=http://localhost:%s/\n' "$ACCESS_MODE" "$PORT"
