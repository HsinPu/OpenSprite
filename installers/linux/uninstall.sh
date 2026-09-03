#!/usr/bin/env bash
set -euo pipefail
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app"
UNIT_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/opensprite.service"
REMOVE_USER_DATA=0
[[ "${EUID:-$(id -u)}" -ne 0 ]] || { echo "Run as the target user, not root or sudo." >&2; exit 1; }
while (($#)); do case "$1" in --remove-user-data) REMOVE_USER_DATA=1; shift;; *) echo "Unknown argument: $1" >&2; exit 2;; esac; done
INSTALL_ROOT="$(realpath -m "$INSTALL_ROOT")"; EXPECTED_SUFFIX="/opensprite/app"
[[ "$INSTALL_ROOT" == *"$EXPECTED_SUFFIX" && ! -L "$INSTALL_ROOT" ]] || { echo "Refusing unsafe install root." >&2; exit 1; }
systemctl --user disable --now opensprite.service 2>/dev/null || true
rm -f -- "$UNIT_FILE"; systemctl --user daemon-reload
rm -rf -- "$INSTALL_ROOT"
if ((REMOVE_USER_DATA == 1)); then
  [[ -r /dev/tty && -w /dev/tty ]] || { echo "User-data removal requires an interactive terminal." >&2; exit 1; }
  USER_DATA_ROOT="$(realpath -m "$HOME/.opensprite")"
  [[ "$USER_DATA_ROOT" == "$(realpath -m "$HOME")/.opensprite" && ! -L "$USER_DATA_ROOT" ]] || { echo "Refusing unsafe user-data root." >&2; exit 1; }
  printf 'Permanently delete %s? Type DELETE: ' "$USER_DATA_ROOT" >/dev/tty
  read -r answer </dev/tty
  [[ "$answer" == "DELETE" ]] && rm -rf -- "$USER_DATA_ROOT" || echo "User data preserved."
fi
echo "OpenSprite application removed."
