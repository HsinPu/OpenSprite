# Custom agent management

## Scope

Expose strict authenticated management operations under `/api/agents` and
implement recoverable TOML/catalog management. Catalog revision is the common
optimistic concurrency token for every mutation. Workspace scope includes its
local entries plus read-only inherited global entries. Batch operations use
explicit IDs, not an implicit live list.

## HTTP boundary

- Reject duplicate/unknown/missing JSON fields and query parameters.
- Limit streaming JSON request bodies before parsing; require JSON content type.
- Validate IDs, scope, pagination bounds and expected revision.
- Hold the Workspace gate through the lifetime of blocking file operations even
  when the originating HTTP task is cancelled.
- Default authentication middleware covers every new route; no public allowlist
  entries are added.

## Verification

123 backend tests passed across management service, HTTP integration, strict
routes, definition/policy/catalog/discovery, AppPaths, runtime and app contracts.
16 frontend adapter tests and TypeScript typecheck passed. Git diff check passed.
The npm launcher printed a sandbox prefix lookup warning but both commands ran
and exited successfully. No dependency installation or upgrade was performed.

The app operation guard now explicitly lists all management routes. The checked-in
`contracts/custom-agents.openapi.json` matches generated agent routes and schemas.
Response validation exceptions for this boundary are deliberately not traced to
runtime logs because they can embed private definition content.

## Implemented service behavior

Catalog/file mutations use a recoverable roll-forward journal, bounded reads,
revision checks and safe paths. Archive operations preserve physical files.
Workspace removal clears agent registrations without deleting workspace content.
The runtime composes the new manager with the shared Workspace gate. Discovery
is a pure bounded snapshot projection, integrated into the parent loop in 0223.

## Subsequent verification

The settings screen and execution UI are now implemented. The full frontend
suite including mobile editor regression passes 393 tests. Browser and live-model
verification are recorded in `0224-custom-agents-release-verification.md`; that
record owns the final completion status, including lifecycle hardening.
