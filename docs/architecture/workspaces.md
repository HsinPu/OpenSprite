# Workspace architecture

## Managed roots and sensitive data

OpenSprite owns one user-visible managed Workspace container outside the
sensitive `.opensprite` data root:

- Windows: `%USERPROFILE%\OpenSprite\workspace`
- Linux: `~/OpenSprite/workspace`

The fixed UUID `00000000-0000-4000-8000-000000000000` identifies the Default
Workspace at `workspace/default`. It cannot be renamed or removed. A new
Workspace named `test` creates `workspace/test`; its immutable directory name
is separate from its later-editable display name. Removing a Workspace removes
only catalog registration and never deletes its directory.

Conversation messages, attachments, generated-output records, SQLite,
credentials, state, logs and cache remain below `.opensprite`. Managed roots
are user project scopes, not a second internal product-data store.

## Catalog v2 and migration

`config/workspaces.json` schema v2 stores catalog revision, active Workspace,
the Default Workspace mount revision, and up to 100 managed Workspace records.
Each record contains UUID, display name, immutable directory name, at most 20
mounts, revision and UTC timestamps. Absolute managed-root paths are derived
from the current user home and are not persisted in the catalog.

On startup the backend creates the container and Default Workspace. A v1
catalog is converted without moving source files: every previous external root
becomes a `legacy-root` read-write mount and a new managed root is created.
Nested legacy roots are imported disabled so no ambiguous authority is
activated. Names or directory names that collide with the new fixed Default
Workspace receive a deterministic `workspace-<UUID prefix>` fallback. The
complete v2 document is validated before atomic replacement; persistence
failure preserves the v1 file and removes only new empty migration directories.
The v1 decoder retains its historical validation rules so old catalogs remain
readable; migration replaces names that do not satisfy the current policy.
Current names reject control, surrogate and unsafe formatting characters while
allowing Unicode ZWNJ and ZWJ required by languages and composed emoji only
when each joiner is internal and not adjacent to another joiner.

Existing first-level managed directories are not adopted implicitly. The
import-candidates endpoint returns a cursor page, and import requires an
explicit user action.

## Mount policy

A Workspace has one writable managed root and zero to twenty external mounts.
Mounts have UUID, NFC-normalized alias, canonical root, `read_only` or
`read_write` access, enabled state and live availability. New mounts default to
read-only.

Enabled roots may not be equal, ancestors or descendants of any managed root
or another enabled mount. Filesystem roots, the home directory and its
ancestors, plus `.opensprite`, the installation directory and any parent that
would expose either protected tree are rejected. Symlinks, junctions and
Windows reparse points are also rejected. Missing or inaccessible saved paths
become unavailable without substitution. Mount mutations are blocked while
the Workspace has a queued, running or cancelling Run.

This release defines authority metadata but adds no file tool. A future
Workspace-aware tool must enforce the immutable snapshot and fail closed.

## Execution and persistence

Each accepted Run holds one `WorkspaceExecutionContext` with the managed root,
mount tuple, permissions, availability and hashes. Retry, Context compaction,
output continuation and Tool rounds reuse that object. Schedules resolve their
stored Workspace ID when an occurrence begins.

SQLite schema v13 stores Workspace ID, revision, display-name snapshot, managed
root hash and mount-manifest hash; it never stores absolute roots. `run.started`
and version-4 Tool receipts include mount aliases, access modes, availability
and root hashes without absolute paths. Existing receipt versions 1–3 remain
verifiable. Full System Prompt logs intentionally contain the complete paths
and remain sensitive; ordinary runtime logs do not.

## Frontend

The Sidebar selects one active Workspace and Conversation pagination remains
Workspace-scoped. Settings can create managed roots, explicitly import existing
first-level directories, and add, edit, enable, disable or remove mounts.
Desktop uses modal editors and the 390px layout uses full-width drawers.
Changing an existing mount path or raising access from read-only to read-write
requires a separate confirmation before the mutation is submitted.

The UI explicitly states that this release does not provide file-content
access. Unavailable roots warn the user but do not disable plain text chat.
