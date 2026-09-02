# Version 0.3.0

## Scope

- Raise the authoritative OpenSprite product/backend version from `0.2.4` to
  `0.3.0` for the first local stdio MCP Client release.
- Keep build information, lock data, `/api/app-info`, About UI and Windows
  installer output aligned to the same version.

## Release boundary

This record documents repository and local-install verification. It does not
create a Git tag, GitHub release or published installer artifact.

The Windows installer isolation test passed and the local service reports
`health=ok` and version `0.3.0`. The install was built from the current
uncommitted working tree, so `/api/app-info` correctly reports the previous
commit revision with `dirty=true`. The active Uvicorn process runs only from
the current `app` directory. Windows kept an older installer rollback directory
locked, so no manual deletion of historical installation backups was attempted.
