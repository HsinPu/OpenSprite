# 0070 Windows installer

## Objective

Create a verifiable Windows installation path for the rebuilt OpenSprite before
removing any legacy installation or user data.

## Changes

- Added an installed FastAPI factory that mounts the built frontend after API
  routes and fails closed when `frontend/dist/index.html` is unavailable.
- Added a guarded Windows installer that stages source, builds the frontend,
  removes build-only Node dependencies, moves to the final app root, creates
  the production Python environment, registers one current-user Scheduled Task
  and verifies health plus the browser index.
- Added rollback of the application directory for dependency, task, startup or
  health failure.
- Added a guarded uninstaller that preserves `.opensprite` unless explicit
  permanent data removal is requested.
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
