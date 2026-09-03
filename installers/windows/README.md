# OpenSprite Windows installer

## Install

Run from the repository root in PowerShell:

```powershell
./installers/windows/install.ps1
```

The installer:

- stages only runtime backend/frontend source and installer files;
- installs production Python dependencies with `uv sync --no-dev`;
- builds the React frontend with `npm ci --ignore-scripts` and `npm run build`;
- removes build-only `node_modules` from the installed application;
- installs to `%LOCALAPPDATA%\OpenSprite\app`;
- registers one `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` entry
  named `OpenSprite` that invokes the installed hidden PowerShell launcher;
- starts the launcher, verifies `/healthz` plus the frontend index, and opens a
  one-time local password setup link on first install;
- rolls the application directory back if dependency setup, task registration,
  startup or health verification fails.

New Windows installs default to trusted-local access and open without a
password. Select password protection explicitly with:

```powershell
./installers/windows/install.ps1 -AccessMode Password
```

Switch an installation to local desktop trust with:

```powershell
./installers/windows/install.ps1 -AccessMode TrustedLocal
```

Existing installations preserve their strict `access-policy.json`. A pre-policy
installation with an existing password or bootstrap remains password-protected;
updates never silently reduce authentication.

The installed UI is available at `http://localhost:8765/`. The backend and
frontend share one loopback origin and one Uvicorn process.

Existing upgrades preserve `~/.opensprite/config/access.json`. To replace a
forgotten local password without deleting conversations, provider credentials,
MCP settings, or logs, run:

```powershell
./installers/windows/install.ps1 -ResetLocalAccess
```

The reset stops the previous backend, replaces only the local-access bootstrap
state, and opens a fresh setup link that expires after 30 minutes.

## Uninstall

```powershell
./installers/windows/uninstall.ps1
```

Uninstall stops the installed process and removes the Run entry and application directory. It
preserves `%USERPROFILE%\.opensprite` by default. Permanent user-data removal
requires the explicit switch:

```powershell
./installers/windows/uninstall.ps1 -RemoveUserData
```

Both scripts enforce the official absolute paths unless their custom-root
switches are explicitly used for isolated testing.

## Isolation test

```powershell
./installers/windows/test.ps1
```

The test installs below a unique system-temporary root without startup
registration or service startup, verifies the frontend build and installed Python
runtime, then uninstalls and removes the temporary root.
