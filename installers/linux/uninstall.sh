#!/usr/bin/env bash
set -euo pipefail
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app"
UNIT_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/opensprite.service"
REMOVE_USER_DATA=0
[[ "${EUID:-$(id -u)}" -ne 0 ]] || { echo "Run as the target user, not root or sudo." >&2; exit 1; }
while (($#)); do case "$1" in --remove-user-data) REMOVE_USER_DATA=1; shift;; *) echo "Unknown argument: $1" >&2; exit 2;; esac; done
INSTALL_ROOT="$(realpath -m "$INSTALL_ROOT")"; EXPECTED_SUFFIX="/opensprite/app"
[[ "$INSTALL_ROOT" == *"$EXPECTED_SUFFIX" && ! -L "$INSTALL_ROOT" ]] || { echo "Refusing unsafe install root." >&2; exit 1; }
USER_DATA_ROOT="$HOME/.opensprite"
APP_EXISTED=0; UNIT_EXISTED=0; DATA_EXISTED=0
[[ ! -e "$INSTALL_ROOT" && ! -L "$INSTALL_ROOT" ]] || APP_EXISTED=1
[[ ! -e "$UNIT_FILE" && ! -L "$UNIT_FILE" ]] || UNIT_EXISTED=1
[[ ! -e "$USER_DATA_ROOT" && ! -L "$USER_DATA_ROOT" ]] || DATA_EXISTED=1
print_removal_status() {
  local label="$1" path="$2" existed="$3" status='Already absent'
  if [[ -e "$path" || -L "$path" ]]; then status='Retained'
  elif ((existed == 1)); then status='Removed'; fi
  printf '  %s: %s -- %s\n' "$label" "$status" "$path"
}
print_uninstall_summary() {
  local result=$?
  printf '\nOpenSprite uninstall summary (current state)\n'
  if ((result != 0)); then printf '  Uninstall stopped before completion. Remaining folders may contain partially removed files.\n'; fi
  print_removal_status 'Application' "$INSTALL_ROOT" "$APP_EXISTED"
  print_removal_status 'User service file' "$UNIT_FILE" "$UNIT_EXISTED"
  print_removal_status 'User data' "$USER_DATA_ROOT" "$DATA_EXISTED"
  printf '%s\n' \
    '    Includes settings, encrypted credentials and key, conversations, schedules,' \
    '    managed workspace files, skills, agents, archives, logs, state and cache.'
  if [[ -e "$USER_DATA_ROOT" ]] && ((result == 0 || REMOVE_USER_DATA == 0)); then printf '  Retained user data can be reused after reinstalling OpenSprite.\n'; fi
  printf '  Not removed: Git, Node.js, uv, shared tool caches, source checkouts and external workspace folders.\n'
  return "$result"
}
trap print_uninstall_summary EXIT
systemctl --user disable --now opensprite.service 2>/dev/null || true
rm -f -- "$UNIT_FILE"; systemctl --user daemon-reload
rm -rf -- "$INSTALL_ROOT"
if ((REMOVE_USER_DATA == 1)); then
  [[ -r /dev/tty && -w /dev/tty ]] || { echo "User-data removal requires an interactive terminal." >&2; exit 1; }
  USER_DATA_ROOT="$(realpath -m "$HOME/.opensprite")"
  [[ "$USER_DATA_ROOT" == "$(realpath -m "$HOME")/.opensprite" && ! -L "$USER_DATA_ROOT" ]] || { echo "Refusing unsafe user-data root." >&2; exit 1; }
  printf 'Permanently delete %s? Type DELETE: ' "$USER_DATA_ROOT" >/dev/tty
  read -r answer </dev/tty
  if [[ "$answer" == "DELETE" ]]; then
    rm -rf -- "$USER_DATA_ROOT"
  else
    echo "User data preserved."
  fi
fi
