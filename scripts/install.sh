#!/usr/bin/env bash
# OpenSprite installer for fresh Linux machines.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/HsinPu/opensprite/main/scripts/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/HsinPu/opensprite/main/scripts/install.sh | bash -s -- --no-start
#
# Installs source code into ~/.local/share/opensprite/opensprite by default
# and links the `opensprite` command into ~/.local/bin. Runtime config/data
# stays under ~/.opensprite.

set -euo pipefail

REPO_URL="${OPENSPRITE_REPO_URL:-https://github.com/HsinPu/opensprite.git}"
BRANCH="${OPENSPRITE_BRANCH:-main}"
INSTALL_DIR="${OPENSPRITE_INSTALL_DIR:-$HOME/.local/share/opensprite/opensprite}"
APP_HOME="${OPENSPRITE_HOME:-$HOME/.opensprite}"
PYTHON_VERSION_MIN="3.11"
NODE_MAJOR=22
NODE_VERSION="${OPENSPRITE_NODE_VERSION:-22.12.0}"
NODE_INSTALL_DIR="${OPENSPRITE_NODE_INSTALL_DIR:-$HOME/.local/share/opensprite/node}"
INSTALL_DEV=0
CREATE_LINK=1
START_SERVICE=1
INSTALL_SYSTEM_PACKAGES=1
INSTALL_BROWSER=1
BROWSER_NO_SANDBOX="${OPENSPRITE_BROWSER_NO_SANDBOX:-1}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { printf "%b==>%b %s\n" "$CYAN" "$NC" "$1"; }
log_success() { printf "%b✓%b %s\n" "$GREEN" "$NC" "$1"; }
log_warn() { printf "%b!%b %s\n" "$YELLOW" "$NC" "$1"; }
log_error() { printf "%bError:%b %s\n" "$RED" "$NC" "$1" >&2; }

usage() {
  cat <<'EOF'
OpenSprite installer

Usage: install.sh [options]

Options:
  --dir PATH       Install repository checkout to PATH.
                   Default: ~/.local/share/opensprite/opensprite
  --branch NAME    Git branch to install. Default: main
  --repo URL       Git repository URL. Default: https://github.com/HsinPu/opensprite.git
  --dev            Install development dependencies with -e ".[dev]".
  --start          Start the background gateway after installation. Default: enabled.
  --no-start       Do not start the background gateway after installation.
  --no-link        Do not create ~/.local/bin/opensprite symlink.
  --no-system      Do not try to install system packages with apt.
  --no-browser     Do not install Chromium/agent-browser browser dependencies.
  -h, --help       Show this help.

Environment overrides:
  OPENSPRITE_REPO_URL
  OPENSPRITE_BRANCH
  OPENSPRITE_INSTALL_DIR
  OPENSPRITE_HOME
  OPENSPRITE_BROWSER_NO_SANDBOX=0  Do not set AGENT_BROWSER_ARGS=--no-sandbox.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --dev)
      INSTALL_DEV=1
      shift
      ;;
    --start)
      START_SERVICE=1
      shift
      ;;
    --no-start)
      START_SERVICE=0
      shift
      ;;
    --no-link)
      CREATE_LINK=0
      shift
      ;;
    --no-system)
      INSTALL_SYSTEM_PACKAGES=0
      shift
      ;;
    --no-browser)
      INSTALL_BROWSER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_error "Unknown option: $1"
      usage >&2
      exit 2
      ;;
  esac
done

detect_os() {
  case "$(uname -s)" in
    Linux*) ;;
    *)
      log_error "This installer currently supports Linux only. Use the manual venv install steps on other platforms."
      exit 1
      ;;
  esac
}

install_system_packages() {
  if [[ "$INSTALL_SYSTEM_PACKAGES" -ne 1 ]]; then
    return 0
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    log_warn "apt-get not found; skipping system package installation."
    return 0
  fi

  local sudo_cmd=()
  if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      log_warn "sudo not found; skipping system package installation."
      return 0
    fi
    sudo_cmd=(sudo)
  fi

  export DEBIAN_FRONTEND=noninteractive
  export NEEDRESTART_MODE=a
  log_info "Installing Debian/Ubuntu system packages"
  "${sudo_cmd[@]}" apt-get update
  "${sudo_cmd[@]}" apt-get install -y git python3 python3-venv python3-pip ca-certificates curl gnupg
}

node_version_parts() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi
  local version
  version="$(node --version 2>/dev/null || true)"
  version="${version#v}"
  IFS=. read -r major minor patch <<< "$version"
  [[ "${major:-}" =~ ^[0-9]+$ ]] || return 1
  [[ "${minor:-}" =~ ^[0-9]+$ ]] || minor=0
  printf '%s %s' "$major" "$minor"
}

node_version_is_usable() {
  local major minor
  read -r major minor < <(node_version_parts) || return 1
  if [[ "$major" -eq 20 && "$minor" -ge 19 ]]; then
    return 0
  fi
  if [[ "$major" -eq 22 && "$minor" -ge 12 ]]; then
    return 0
  fi
  if [[ "$major" -gt 22 ]]; then
    return 0
  fi
  return 1
}

npm_is_available() {
  command -v npm >/dev/null 2>&1
}

activate_local_node() {
  if [[ -x "$NODE_INSTALL_DIR/bin/node" ]]; then
    export PATH="$NODE_INSTALL_DIR/bin:$PATH"
  fi
}

node_linux_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf 'x64' ;;
    aarch64|arm64) printf 'arm64' ;;
    *) return 1 ;;
  esac
}

install_local_node() {
  local arch
  if ! arch="$(node_linux_arch)"; then
    log_warn "Unsupported CPU architecture for local Node.js install: $(uname -m)"
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1 || ! command -v tar >/dev/null 2>&1; then
    log_warn "curl and tar are required for local Node.js install."
    return 1
  fi

  local archive="node-v${NODE_VERSION}-linux-${arch}.tar.xz"
  local url="https://nodejs.org/dist/v${NODE_VERSION}/${archive}"
  local temp_dir
  temp_dir="$(mktemp -d)"

  log_info "Installing local Node.js ${NODE_VERSION} with npm"
  if ! curl -fsSL "$url" -o "$temp_dir/$archive"; then
    rm -rf "$temp_dir"
    log_warn "Could not download Node.js from $url"
    return 1
  fi

  rm -rf "$NODE_INSTALL_DIR"
  mkdir -p "$NODE_INSTALL_DIR"
  if ! tar -xJf "$temp_dir/$archive" -C "$NODE_INSTALL_DIR" --strip-components=1; then
    rm -rf "$temp_dir" "$NODE_INSTALL_DIR"
    log_warn "Could not extract Node.js archive; install xz/tar support or install Node.js manually."
    return 1
  fi
  rm -rf "$temp_dir"
  activate_local_node
  return 0
}

node_package_manager() {
  if command -v apt-get >/dev/null 2>&1; then
    printf 'apt'
    return 0
  fi
  if command -v dnf >/dev/null 2>&1; then
    printf 'dnf'
    return 0
  fi
  if command -v yum >/dev/null 2>&1; then
    printf 'yum'
    return 0
  fi
  return 1
}

ensure_node() {
  activate_local_node

  if node_version_is_usable && npm_is_available; then
    log_success "Node.js $(node --version) and npm $(npm --version) found"
    return 0
  fi

  local package_manager=""
  package_manager="$(node_package_manager || true)"

  if [[ "$INSTALL_SYSTEM_PACKAGES" -ne 1 ]]; then
    log_warn "Node.js 20.19+ or 22.12+ with npm is required for the Web UI build."
    if install_local_node && node_version_is_usable && npm_is_available; then
      log_success "Node.js $(node --version) and npm $(npm --version) ready"
      return 0
    fi
    log_info "Install Node.js 22 and npm manually, then run: opensprite update --restart"
    return 0
  fi
  if [[ -z "$package_manager" ]]; then
    log_warn "No supported package manager found for Node.js install."
    if install_local_node && node_version_is_usable && npm_is_available; then
      log_success "Node.js $(node --version) and npm $(npm --version) ready"
      return 0
    fi
    log_warn "Install Node.js 20.19+ or 22.12+ with npm manually for the Web UI build."
    return 0
  fi

  local sudo_cmd=()
  if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      log_warn "sudo not found; install Node.js 20.19+ or 22.12+ with npm manually for the Web UI build."
      if install_local_node && node_version_is_usable && npm_is_available; then
        log_success "Node.js $(node --version) and npm $(npm --version) ready"
        return 0
      fi
      return 0
    fi
    sudo_cmd=(sudo)
  fi

  if node_version_is_usable; then
    log_info "Node.js $(node --version) is installed but npm was not found; installing Node.js $NODE_MAJOR with npm"
  elif command -v node >/dev/null 2>&1; then
    log_info "Node.js $(node --version) is too old for the Web UI; installing Node.js $NODE_MAJOR"
  else
    log_info "Node.js not found; installing Node.js $NODE_MAJOR"
  fi
  local setup_cmd=(bash -)
  if [[ "${#sudo_cmd[@]}" -gt 0 ]]; then
    setup_cmd=("${sudo_cmd[@]}" -E bash -)
  fi
  if [[ "$package_manager" == "apt" ]]; then
    if ! { curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | "${setup_cmd[@]}" && "${sudo_cmd[@]}" apt-get install -y nodejs; }; then
      log_warn "System Node.js install failed; trying local Node.js install."
      install_local_node || true
    fi
  elif [[ "$package_manager" == "dnf" ]]; then
    if ! { curl -fsSL "https://rpm.nodesource.com/setup_${NODE_MAJOR}.x" | "${setup_cmd[@]}" && "${sudo_cmd[@]}" dnf install -y nodejs; }; then
      log_warn "System Node.js install failed; trying local Node.js install."
      install_local_node || true
    fi
  else
    if ! { curl -fsSL "https://rpm.nodesource.com/setup_${NODE_MAJOR}.x" | "${setup_cmd[@]}" && "${sudo_cmd[@]}" yum install -y nodejs; }; then
      log_warn "System Node.js install failed; trying local Node.js install."
      install_local_node || true
    fi
  fi

  if ! node_version_is_usable; then
    log_warn "Node.js is still too old or unavailable; Web UI build may fail."
    return 0
  fi
  if ! npm_is_available; then
    log_warn "npm is still unavailable after installing Node.js; trying local Node.js install."
    install_local_node || true
  fi
  if ! npm_is_available; then
    log_warn "npm is still unavailable; Web UI build may fail."
    return 0
  fi
  log_success "Node.js $(node --version) and npm $(npm --version) ready"
}

find_browser_executable() {
  local candidate resolved
  for candidate in \
    "${AGENT_BROWSER_EXECUTABLE_PATH:-}" \
    chromium \
    chromium-browser \
    google-chrome-stable \
    google-chrome \
    chrome \
    /usr/bin/chromium \
    /usr/bin/chromium-browser \
    /usr/bin/google-chrome-stable \
    /usr/bin/google-chrome \
    /snap/bin/chromium; do
    [[ -n "$candidate" ]] || continue
    if [[ "$candidate" == */* ]]; then
      [[ -x "$candidate" ]] || continue
      resolved="$candidate"
    else
      resolved="$(command -v "$candidate" 2>/dev/null || true)"
      [[ -n "$resolved" ]] || continue
    fi
    printf '%s' "$resolved"
    return 0
  done
  return 1
}

ensure_browser_no_sandbox_arg() {
  if [[ "$BROWSER_NO_SANDBOX" == "0" || "$BROWSER_NO_SANDBOX" == "false" ]]; then
    return 0
  fi
  case ",${AGENT_BROWSER_ARGS:-}," in
    *,--no-sandbox,*) ;;
    *)
      if [[ -n "${AGENT_BROWSER_ARGS:-}" ]]; then
        export AGENT_BROWSER_ARGS="${AGENT_BROWSER_ARGS},--no-sandbox"
      else
        export AGENT_BROWSER_ARGS="--no-sandbox"
      fi
      ;;
  esac
}

install_system_browser_package() {
  if [[ "$INSTALL_SYSTEM_PACKAGES" -ne 1 ]]; then
    return 1
  fi

  local sudo_cmd=()
  if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      return 1
    fi
    sudo_cmd=(sudo)
  fi

  if command -v apt-get >/dev/null 2>&1; then
    log_info "Installing Chromium with apt"
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a
    if command -v apt-cache >/dev/null 2>&1 && apt-cache show chromium >/dev/null 2>&1; then
      "${sudo_cmd[@]}" apt-get install -y chromium && return 0
    fi
    if command -v apt-cache >/dev/null 2>&1 && apt-cache show chromium-browser >/dev/null 2>&1; then
      "${sudo_cmd[@]}" apt-get install -y chromium-browser && return 0
    fi
    "${sudo_cmd[@]}" apt-get install -y chromium && return 0
    return 1
  fi

  if command -v dnf >/dev/null 2>&1; then
    log_info "Installing Chromium with dnf"
    "${sudo_cmd[@]}" dnf install -y chromium && return 0
    return 1
  fi

  if command -v yum >/dev/null 2>&1; then
    log_info "Installing Chromium with yum"
    "${sudo_cmd[@]}" yum install -y chromium && return 0
    return 1
  fi

  return 1
}

install_agent_browser_chrome() {
  if ! command -v npx >/dev/null 2>&1; then
    return 1
  fi
  if [[ "$INSTALL_SYSTEM_PACKAGES" -eq 1 ]]; then
    log_info "Installing agent-browser managed Chrome runtime with system dependencies"
    npx --yes agent-browser install --with-deps
  else
    log_info "Installing agent-browser managed Chrome runtime"
    npx --yes agent-browser install
  fi
}

run_agent_browser_doctor() {
  if ! command -v npx >/dev/null 2>&1; then
    return 0
  fi

  log_info "Checking agent-browser runtime"
  if command -v timeout >/dev/null 2>&1; then
    timeout 60s npx --yes agent-browser doctor || log_warn "agent-browser doctor did not pass within 60s; browser tools may need manual setup."
  else
    npx --yes agent-browser doctor || log_warn "agent-browser doctor reported issues; browser tools may need manual setup."
  fi
}

ensure_browser_runtime() {
  if [[ "$INSTALL_BROWSER" -ne 1 ]]; then
    return 0
  fi

  local browser_path=""
  if browser_path="$(find_browser_executable)"; then
    export AGENT_BROWSER_EXECUTABLE_PATH="${AGENT_BROWSER_EXECUTABLE_PATH:-$browser_path}"
    log_success "Browser runtime found: ${AGENT_BROWSER_EXECUTABLE_PATH}"
  else
    log_info "Chromium/Chrome was not found; installing browser runtime"
    install_system_browser_package || install_agent_browser_chrome || log_warn "Could not install Chromium automatically; browser tools may fail until Chromium/Chrome is installed."
    if browser_path="$(find_browser_executable)"; then
      export AGENT_BROWSER_EXECUTABLE_PATH="${AGENT_BROWSER_EXECUTABLE_PATH:-$browser_path}"
      log_success "Browser runtime ready: ${AGENT_BROWSER_EXECUTABLE_PATH}"
    else
      log_warn "No system Chromium/Chrome executable found after install. agent-browser may still use its managed browser if doctor passes."
    fi
  fi

  ensure_browser_no_sandbox_arg
  run_agent_browser_doctor
}

find_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      then
        printf '%s' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi
  log_error "git is required but was not found. Install git and re-run this installer."
  exit 1
}

clone_or_update_repo() {
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log_info "Updating existing checkout: $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
    return 0
  fi

  if [[ -e "$INSTALL_DIR" ]]; then
    log_error "Install path exists but is not a git checkout: $INSTALL_DIR"
    exit 1
  fi

  log_info "Cloning OpenSprite into $INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
}

install_python_package() {
  local python_bin="$1"
  cd "$INSTALL_DIR"
  if [[ ! -d ".venv" ]]; then
    log_info "Creating virtual environment"
    "$python_bin" -m venv .venv
  fi

  log_info "Installing OpenSprite"
  .venv/bin/python -m pip install --upgrade pip
  if [[ "$INSTALL_DEV" -eq 1 ]]; then
    .venv/bin/python -m pip install -e ".[dev]"
  else
    .venv/bin/python -m pip install -e .
  fi
}

install_web_frontend() {
  local web_dir="$INSTALL_DIR/apps/web"
  if [[ ! -f "$web_dir/package.json" ]]; then
    return 0
  fi

  if ! command -v npm >/dev/null 2>&1; then
    log_error "npm is required to build the Web UI. The installer could not install npm automatically; install Node.js 20.19+ or 22.12+ with npm and re-run this installer."
    exit 1
  fi

  log_info "Installing Web UI dependencies"
  if [[ -f "$web_dir/package-lock.json" ]]; then
    npm --prefix "$web_dir" ci
  else
    npm --prefix "$web_dir" install
  fi

  log_info "Building Web UI"
  npm --prefix "$web_dir" run build
  log_success "Built Web UI"
}

detect_shell_config() {
  case "$(basename "${SHELL:-bash}")" in
    zsh) printf '%s' "$HOME/.zshrc" ;;
    bash) printf '%s' "$HOME/.bashrc" ;;
    *) printf '%s' "$HOME/.profile" ;;
  esac
}

persist_browser_environment() {
  if [[ "$INSTALL_BROWSER" -ne 1 ]]; then
    return 0
  fi

  local shell_config
  shell_config="$(detect_shell_config)"
  touch "$shell_config"

  if [[ -n "${AGENT_BROWSER_EXECUTABLE_PATH:-}" ]] && ! grep -v '^[[:space:]]*#' "$shell_config" | grep -qE '^export[[:space:]]+AGENT_BROWSER_EXECUTABLE_PATH='; then
    {
      printf '\n'
      printf '# OpenSprite browser runtime\n'
      printf 'export AGENT_BROWSER_EXECUTABLE_PATH=%q\n' "$AGENT_BROWSER_EXECUTABLE_PATH"
    } >> "$shell_config"
    log_success "Added browser executable path to $shell_config"
  fi

  if [[ "${AGENT_BROWSER_ARGS:-}" == *"--no-sandbox"* ]] && ! grep -v '^[[:space:]]*#' "$shell_config" | grep -qE 'AGENT_BROWSER_ARGS=.*--no-sandbox'; then
    {
      printf '\n'
      printf '# OpenSprite browser runtime flags\n'
      printf 'export AGENT_BROWSER_ARGS=%q\n' "$AGENT_BROWSER_ARGS"
    } >> "$shell_config"
    log_success "Added browser no-sandbox flag to $shell_config"
  fi
}

ensure_default_config() {
  local config_path="$APP_HOME/opensprite.json"
  if [[ -f "$config_path" ]]; then
    return 0
  fi

  log_info "Creating default OpenSprite config"
  OPENSPRITE_CONFIG_PATH="$config_path" "$INSTALL_DIR/.venv/bin/python" - <<'PY'
import os
from pathlib import Path

from opensprite.config import Config

path = Path(os.environ["OPENSPRITE_CONFIG_PATH"]).expanduser()
Config.copy_template(path)
PY
}

systemd_user_available() {
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1
}

enable_user_linger() {
  if ! command -v loginctl >/dev/null 2>&1; then
    log_warn "loginctl not found; the user service may only start after login."
    return 0
  fi
  if [[ -z "${USER:-}" ]]; then
    log_warn "USER is not set; run 'loginctl enable-linger <user>' if you need startup before login."
    return 0
  fi
  if loginctl enable-linger "$USER" >/dev/null 2>&1; then
    log_success "Enabled user linger for $USER"
  else
    log_warn "Could not enable user linger automatically; run: loginctl enable-linger $USER"
  fi
}

persist_systemd_environment() {
  if ! systemd_user_available; then
    return 0
  fi

  local env_dir="$HOME/.config/environment.d"
  local env_file="$env_dir/opensprite.conf"
  mkdir -p "$env_dir"
  {
    printf '# OpenSprite service environment\n'
    printf 'PATH=%s\n' "$PATH"
    if [[ -n "${AGENT_BROWSER_EXECUTABLE_PATH:-}" ]]; then
      printf 'AGENT_BROWSER_EXECUTABLE_PATH=%s\n' "$AGENT_BROWSER_EXECUTABLE_PATH"
    fi
    if [[ -n "${AGENT_BROWSER_ARGS:-}" ]]; then
      printf 'AGENT_BROWSER_ARGS=%s\n' "$AGENT_BROWSER_ARGS"
    fi
  } > "$env_file"
  systemctl --user import-environment PATH AGENT_BROWSER_EXECUTABLE_PATH AGENT_BROWSER_ARGS >/dev/null 2>&1 || true
  log_success "Wrote systemd user environment: $env_file"
}

setup_command_link() {
  if [[ "$CREATE_LINK" -ne 1 ]]; then
    return 0
  fi
  local link_dir="$HOME/.local/bin"
  mkdir -p "$link_dir"
  ln -sfn "$INSTALL_DIR/.venv/bin/opensprite" "$link_dir/opensprite"
  log_success "Linked opensprite -> $link_dir/opensprite"

  local shell_config=""
  shell_config="$(detect_shell_config)"
  touch "$shell_config"

  case ":$PATH:" in
    *":$link_dir:"*) ;;
    *)
      log_warn "$link_dir is not on PATH for this shell."
      if ! grep -v '^[[:space:]]*#' "$shell_config" | grep -qE 'PATH=.*\.local/bin'; then
        {
          printf '\n'
          printf '# OpenSprite command path\n'
          printf 'export PATH="$HOME/.local/bin:$PATH"\n'
        } >> "$shell_config"
        log_success "Added ~/.local/bin to PATH in $shell_config"
      fi
      ;;
  esac

  if [[ -x "$NODE_INSTALL_DIR/bin/node" ]] && ! grep -v '^[[:space:]]*#' "$shell_config" | grep -qF "$NODE_INSTALL_DIR/bin"; then
    {
      printf '\n'
      printf '# OpenSprite local Node.js path\n'
      printf 'export PATH="%s/bin:$PATH"\n' "$NODE_INSTALL_DIR"
    } >> "$shell_config"
    log_success "Added local Node.js to PATH in $shell_config"
  fi

  if [[ ":$PATH:" != *":$link_dir:"* || -x "$NODE_INSTALL_DIR/bin/node" ]]; then
    log_info "Reload your shell or run: source $shell_config"
  fi
}

verify_install() {
  log_info "Verifying CLI"
  "$INSTALL_DIR/.venv/bin/opensprite" --version
}

maybe_start_service() {
  if [[ "$START_SERVICE" -ne 1 ]]; then
    return 0
  fi

  ensure_default_config
  persist_systemd_environment

  if systemd_user_available; then
    log_info "Installing OpenSprite systemd user service"
    "$INSTALL_DIR/.venv/bin/opensprite" service stop >/dev/null 2>&1 || true
    enable_user_linger
    if "$INSTALL_DIR/.venv/bin/opensprite" service install --config "$APP_HOME/opensprite.json" --start; then
      "$INSTALL_DIR/.venv/bin/opensprite" service status
      return 0
    fi
    log_warn "Systemd user service install failed; falling back to a detached background process."
  fi

  log_info "Starting OpenSprite detached background gateway"
  "$INSTALL_DIR/.venv/bin/opensprite" service stop >/dev/null 2>&1 || true
  "$INSTALL_DIR/.venv/bin/opensprite" service start --config "$APP_HOME/opensprite.json"
  "$INSTALL_DIR/.venv/bin/opensprite" service status
}

print_success() {
  cat <<EOF

OpenSprite installed successfully.

Code: $INSTALL_DIR
Data: $APP_HOME

Commands:
  opensprite update
  opensprite service start
  opensprite service status
  opensprite service stop

On Linux systems with systemd user services, the installer enables
opensprite-gateway.service so the gateway starts again after reboot.

Uninstall while keeping ~/.opensprite data:
  curl -fsSL https://raw.githubusercontent.com/HsinPu/opensprite/main/scripts/uninstall.sh | bash

Logs:
  tail -f ~/.opensprite/logs/gateway.log

If 'opensprite' is not found, run:
  export PATH="\$HOME/.local/bin:\$PATH"

EOF
}

main() {
  log_info "OpenSprite installer"
  detect_os
  install_system_packages
  ensure_node
  ensure_git

  local python_bin
  if ! python_bin="$(find_python)"; then
    log_error "Python $PYTHON_VERSION_MIN+ is required. Install Python 3.11+ and re-run this installer."
    exit 1
  fi
  log_success "Using $($python_bin --version)"

  clone_or_update_repo
  install_python_package "$python_bin"
  install_web_frontend
  ensure_browser_runtime
  setup_command_link
  persist_browser_environment
  verify_install
  maybe_start_service
  print_success
}

main
