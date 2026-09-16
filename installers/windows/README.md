# OpenSprite Windows installer

## Download installer (release assets must be published first)

`bootstrap.ps1` downloads a stable GitHub Release from **HsinPu/OpenSprite**,
checks SHA-256, validates ZIP paths, invokes the existing installer and cleans
its download directory. Git is not required on the destination machine.
There is no fallback to `main`, prereleases or another repository.

After a release containing these assets is published, download
`OpenSprite-install.ps1` from that release, inspect it, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\OpenSprite-install.ps1
```

Use `-Version X.Y.Z` to pin a release. By default it resolves `latest` once.
Use the same command to update an existing installation. No user data or access
mode is reset. `-SkipBrowserLaunch` suppresses the final browser launch.

For a one-line entry **after publication**, from PowerShell:

```powershell
& ([scriptblock]::Create((Invoke-WebRequest -UseBasicParsing 'https://github.com/HsinPu/OpenSprite/releases/latest/download/OpenSprite-install.ps1').Content))
```

This executes code from the official repository; only use it if you trust that
source. Downloading and inspecting the script first is the more reviewable option.
The initial script is trusted through HTTPS/GitHub; the archive checksum confirms
integrity, not an independent publisher signature. These URLs will not work until
the first matching public Release exists. Local implementation does not publish it.

Missing Node.js/npm or uv is reported before touching the application. Interactive
users may consent to winget installation; `-InstallPrerequisites` supplies that
consent explicitly (including package/source agreements). `-NonInteractive` fails
without consent. Old Node versions require a manual upgrade; no forced overwrite.
No winget means manual installation and retry. The installer does not remove these
tools, change the machine execution policy or clean shared npm/uv caches.

Downloads have time/size limits. Invalid checksums, links, duplicate or unsafe ZIP
paths stop installation. One per-session installation mutex also protects direct
installer runs. Failures retain only a short `failure.txt` stage report in the
download temp directory if cleanup succeeds; console output contains the detailed
error. No credentials or signed download URLs are persisted in that report.

## Release maintainers

From a clean committed checkout, run `./installers/windows/package.ps1`.
It creates `dist/release/OpenSprite-X.Y.Z-windows.zip`, its `.sha256`, and
`OpenSprite-install.ps1`. The allowlisted source package excludes tests, Git data,
dependencies and generated files, and records the exact commit. It is built on
the destination machine, not a prebuilt EXE.

The manually dispatched `Windows release package` GitHub workflow takes an
**existing** stable `vX.Y.Z` tag, verifies package version, runs Windows tests and
creates a **draft** Release. It does not create tags, replace existing releases
or publish without human review. The tag must include the new installer files.
Run a clean-Windows smoke test before publishing the draft.

## Install

Prerequisites: Node.js 20.19+ (20.x) or 22.12+, npm, and uv must be on PATH.
Both local and download installers check these before stopping an existing installation.
Missing packages can be installed with winget after an interactive confirmation,
or with explicit consent using `-InstallPrerequisites`. Add `-InstallGit` to include
Git when missing; Git remains optional for source/ZIP installation. These switches
also accept package/source agreements. `-NonInteractive` fails without consent.
Unsupported existing Node.js versions require a manual upgrade. Missing npm offers
the Node.js LTS package; if npm remains unavailable, repair Node.js and retry.
No winget means manual installation. PATH is refreshed after installation; tools
are rechecked before proceeding. OS elevation prompts may still appear.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installers\windows\install.ps1 -InstallPrerequisites -InstallGit
```

`-WhatIf` on the local installer does not install prerequisites.

On failed upgrades, recovery restores saved access state before restarting the
previous application. Failed program files may remain in `.app-failed-*` next
to the application. If Windows also blocks renaming, the previous backup is
preserved and recovery warnings identify the affected step; automatic restart
is withheld when application or access-state recovery is incomplete.

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

Frontend build and Python dependency preparation occur before stopping the old
service. Python environments are recreated at their final path from the warmed
cache rather than relocated. Locked preparation/rollback directories are retained
with a warning. After healthy startup, recognized old `.app-previous-*` directories
are retried; failed-install recovery directories are never swept automatically.

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

Scheduled Agent runs depend on the current-user startup entry. They execute only
after that Windows user has signed in and OpenSprite is running; they do not run
while the computer is powered off, asleep, or before user sign-in.

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

Offline tests (no real installation or dependency installation):

```powershell
./installers/windows/test-bootstrap.ps1
./installers/windows/test-package.ps1
```

```powershell
./installers/windows/test.ps1
```

The test installs below a unique system-temporary root without startup
registration or service startup, verifies the frontend build and installed Python
runtime, then uninstalls and removes the temporary root.
