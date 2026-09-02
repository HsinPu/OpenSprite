# Native local path picker

## Objective

Allow users to choose stdio MCP executable and working-directory paths with a
native Windows or Linux dialog while retaining manual path input.

## Changes

- Added strict `POST /api/local-paths/pick` with executable and directory modes,
  explicit cancellation, busy, unavailable, and invalid-selection behavior.
- Added a Windows `IFileOpenDialog` adapter and a Linux XDG Desktop Portal
  FileChooser adapter. Unsupported or headless systems fail closed to manual input.
- Added Ant Design browse controls beside both stdio path inputs with loading,
  cancellation preservation, localized errors, and unchanged second confirmation.
- Added a conditional, pinned Linux `dbus-next` dependency.

## Public impact

The new endpoint returns only the path explicitly selected by the user. It does
not accept an initial path, enumerate the filesystem, persist data, or appear on
the Streamable HTTP form.

## Verification

- Backend service, API, Windows COM construction, Linux Portal fake, security,
  contract, and route tests.
- Frontend API, component, cancellation, i18n, typecheck, and production build.
- Full backend suite passed with 598 tests and 2 existing conditional skips;
  frontend Vitest passed with 230 tests. Windows installer isolation passed.

## Remaining work

The Linux adapter is contract- and fake-tested on Windows; a real Linux desktop
Portal smoke test remains pending because the repository has no Linux installer
or Linux execution harness yet.
