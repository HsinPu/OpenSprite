# Windows installation

## Ownership

`installers/windows/install.ps1` is the authoritative Windows deployment path.
It installs program files below `%LOCALAPPDATA%\OpenSprite\app` and never treats
`%USERPROFILE%\.opensprite` as application code. The uninstaller preserves the
user-data root unless `-RemoveUserData` is explicitly supplied.

## Installed runtime

`opensprite_backend.installed_runtime:create_installed_app` composes the same
secured system runtime used in development and mounts `frontend/dist` after all
API routes. One Uvicorn process therefore owns:

- the built React index and hashed assets;
- loopback HTTP settings, Provider and Agent Chat APIs;
- Run-event SSE;
- the single-writer `.opensprite` data boundary.

The default frontend path is resolved relative to the deployed tree:
`<app>/frontend/dist`. A missing directory or `index.html` fails before the
server binds. API routes remain registered before the `/` static mount.

## Deployment transaction

The installer builds in a sibling staging directory. Frontend dependencies are
used only for the build and removed before deployment. The staging tree is
moved to the final application path before `uv sync --no-dev`, because Windows
virtual-environment launchers contain final-path information and must not be
moved after creation.

An existing application root is held in a temporary rollback directory. Startup
registration, launch and health failure remove the new root and restore the
previous root. The rollback root is deleted only after success.

## Background lifecycle

One `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` value named
`OpenSprite` invokes the installed `launch.ps1` through hidden Windows
PowerShell at logon. The launcher verifies the official install root, rejects a
port owned by another process, treats the matching installed backend as already
running, and otherwise starts Uvicorn with:

```text
opensprite_backend.installed_runtime:create_installed_app
--factory --host 127.0.0.1 --port 8765 --no-proxy-headers
```

No reloader, additional worker, proxy-header trust, Scheduled Task, VBS/CMD
launcher or legacy Startup file is created. Installation succeeds only after both
`/healthz` and `/` respond correctly.

## Safety

- Official install and data roots are resolved to absolute paths and compared
  case-insensitively before removal.
- Custom roots require explicit test-only switches.
- User data is never removed as part of ordinary install or uninstall.
- `-RemoveUserData` is an explicit permanent deletion operation covering the
  complete sensitive `.opensprite` root.
- Linux must eventually implement the same installation, single-process,
  health, rollback and default data-preservation behavior.
