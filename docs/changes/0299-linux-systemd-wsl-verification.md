# Linux systemd startup and WSL lifecycle verification

An actual install from revision `0145460c` built successfully on Ubuntu but
failed when systemd loaded the generated service. The journal reported
`WorkingDirectory= path is not absolute`: this directive treated the surrounding
double quotes as part of the directory. The isolated installer test had skipped
unit generation, so it did not detect the failure.

The installer now writes the absolute `WorkingDirectory=` value without quotes
and retains the executable quoting in `ExecStart=`. Test installations generate
the same unit inside their temporary root without registering or starting it.
The Linux test builds in a path containing spaces and checks that actual unit
with `systemd-analyze --user verify`.

Linger detection now supplies the target username to `loginctl show-user`.
Without it, a WSL command outside an interactive login session returned no value
even though the account had `Linger=yes`. The installer still only checks and
warns; it does not enable linger itself.

## Environment

- Windows 10 build 19045, WSL 2.7.14.0, kernel 6.18.33.2-2.
- Ubuntu 24.04.5 LTS, dedicated non-root account `opensprite-test`.
- Node.js 22.23.2, npm 10.9.8, uv 0.12.15, Python 3.12.3.
- GitHub `main` at `0145460c`, followed by the installer changes in this slice.
- The Ubuntu image, Node.js archive and uv archive matched their official
  SHA-256 values before installation. WSL's first Ubuntu download was rejected
  for a checksum mismatch; a complete direct download passed validation.
- The test account's user manager and linger were enabled during environment
  setup. Its Linux home and product data are separate from Windows user data.

## Verification

- `bash -n` passed for the Linux installer, uninstaller and test script.
- `uv run --project backend bash installers/linux/test.sh` passed the real
  frontend build, Python deployment, access helper checks, and generated-unit
  validation in a temporary path containing spaces.
- 34 backend tests passed with warnings treated as errors: Linux installer,
  authentication and installed runtime tests.
- Frontend installation with `npm ci --ignore-scripts` succeeded. All 555 tests
  in 64 files passed with `npm test -- --run --maxWorkers=2`. The initial default
  parallel run had 12 timeouts and a worker exit; the two-worker rerun used the
  existing test timeouts and required no frontend code changes.
- The actual installation became `active` and `enabled`; `/healthz`, app info,
  trusted-local access status, frontend HTML and its JavaScript asset returned
  successfully. The one Uvicorn listener was bound to `127.0.0.1:8765`.
- Re-running the installer without an access-mode argument preserved the
  trusted-local policy and saved general settings while replacing the installed
  build. The tracked file hashes stayed identical. A service restart passed the
  same HTTP checks.
- Before uninstall, the exact application path was verified and the service
  stopped. Default uninstall removed the application, unit and listener while
  preserving all three existing user-data files byte-for-byte. No user-data
  deletion option was used. Reinstallation preserved the settings and left the
  service active and enabled.
- Terminating and reopening this Ubuntu distribution started the enabled
  service again. Windows `http://localhost:8765/` served the frontend and its
  health endpoint successfully through WSL forwarding.
- The data root/config directory had mode `0700`; the settings file had `0600`.
  Successful install/update/reinstall logs contained no false linger warning.
- Python compilation, offline lock check, dependency compatibility check and
  `git diff --check` passed. Builds reported the existing large frontend chunk
  warning.

This verifies the trusted-local lifecycle in WSL Ubuntu. It does not claim a
manual browser interaction review, an interactive password/SSH setup test, or
coverage of other Linux distributions. Linux still requires prepared tools and
source; it does not yet have the Windows source-download/dependency bootstrap.

The dedicated Ubuntu account retains the installed application and its test
settings. Start that environment from Windows with `wsl -d Ubuntu-24.04` and
keep the Linux session open while using `http://localhost:8765/`; the systemd
service starts when the distribution starts.
