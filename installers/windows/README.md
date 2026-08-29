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
- starts the launcher and verifies `/healthz` plus the frontend index;
- rolls the application directory back if dependency setup, task registration,
  startup or health verification fails.

The installed UI is available at `http://127.0.0.1:8765/`. The backend and
frontend share one loopback origin and one Uvicorn process.

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
