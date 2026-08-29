# 0070 Windows installer

## Objective

Create a verifiable Windows installation path for the rebuilt OpenSprite before
removing any legacy installation or user data.

## Changes

- Added an installed FastAPI factory that mounts the built frontend after API
  routes and fails closed when `frontend/dist/index.html` is unavailable.
- Added a guarded Windows installer that stages source, builds the frontend,
  removes build-only Node dependencies, moves to the final app root, creates
  the production Python environment, registers one current-user Run entry with
  a guarded hidden PowerShell launcher, and verifies health plus the browser index.
- Added rollback of the application directory for dependency, startup registration, launch or
  health failure.
- Existing installations stop only their path-matched installed runtime before
  application-directory replacement, allowing Windows venv files to move safely.
- Runtime stop tolerates an already-exited matching child, and failed cutover
  restores the previous Run value and relaunches the prior installed app.
- Successful cutover retries transient rollback-directory locks and does not
  undo a healthy new installation solely because cleanup is temporarily locked.
- Frontend-path validation no longer imports system composition or cryptography;
  uninstall and isolation cleanup retry transient Windows DLL scan locks.
- The isolation test quarantines production `.pyd` binaries before exercising
  full-root uninstall because this host's security scanner can retain newly
  created native modules after every process has exited. A remaining quarantine
  emits an explicit warning rather than a false cleanup claim.
- Added a guarded uninstaller that preserves `.opensprite` unless explicit
  permanent data removal is requested.
- Scheduled Task registration was rejected by this non-admin Windows account;
  the final design uses the per-user Run registry and requires no elevation.
- Added a system-temporary isolation test covering build, install shape,
  installed Python import, absence of runtime `node_modules` and uninstall.
- Documented the single-process installed runtime, official paths and the
  still-pending Linux installer.

## Verification

- Full backend verification passed: 391 tests with two platform-specific skips,
  compileall, offline lock and dependency checks.
- Full frontend verification passed: 15 test files and 128 tests, TypeScript
  typecheck and the Vite production build.
- Installed runtime tests passed. A real single-process smoke on temporary port
  8876 returned health `ok`, HTTP 200 with the OpenSprite index and the expected
  Conversation Settings API response.
- All Windows PowerShell files passed the parser.
- The isolated Windows build/install/uninstall test passed outside the official
  application and user-data roots.
- A live application update preserved encrypted credentials and the current
  SQLite database, restarted healthy on port 8765, and removed the prior app
  tree after a short service stop released the final Windows DLL lock.
