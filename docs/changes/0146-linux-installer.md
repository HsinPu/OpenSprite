# Linux current-user installer

## Objective

Install OpenSprite safely for one Linux user with local-desktop trust or remote
SSH password protection.

## Changes

- Added staged current-user install, rollback, uninstall, systemd user service,
  loopback health check, and strict access-mode preservation.
- Added an installer-only Python helper that reuses backend access stores and
  writes one-time setup URLs only to `/dev/tty`.
- Added SSH Tunnel documentation, root/symlink/path guards, restrictive modes,
  and explicit data-removal confirmation.
- Added portable Python helper tests, Bash syntax checks, and a Linux-only full
  isolation script.

## Public impact

Linux users can select `trusted_local` for a graphical desktop or
`password_required` for SSH access. Program uninstall preserves
`~/.opensprite` by default.

## Verification

- Portable helper pytest and Python compile checks on Windows.
- Git Bash syntax validation for all shell scripts.
- `installers/linux/test.sh` defines the full Linux build/isolation gate.

## Remaining work

The full Linux isolation script requires a real Linux host and has not been run
on this Windows machine. Public HTTPS/server mode and system linger remain out
of scope.
