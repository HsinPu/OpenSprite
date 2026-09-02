# Version 0.5.0

## Objective

OpenSprite 0.5.0 adds encrypted manual Bearer-token authentication for
Streamable HTTP MCP connections while retaining the no-authentication and local
stdio paths.

## Changes

The authoritative version remains in `backend/pyproject.toml`; backend app-info,
build-info tests, the lockfile, and Windows installer expectations stay aligned
with that value.

## Public impact

`GET /api/app-info` and the settings About view report version `0.5.0` after a
new installation or update.

## Verification

- Backend app-info and build-info tests passed.
- Offline lock consistency and the Windows installer isolation test passed.

## Remaining work

Publishing and updating the installed desktop runtime are separate explicit
operations.
