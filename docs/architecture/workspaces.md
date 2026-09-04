# Workspace architecture

## Purpose and boundary

A Workspace gives web chat, durable schedules, future Skills and future channel
adapters one explicit local execution scope. A user Workspace binds one UUID to
one canonical existing directory. The reserved unassigned Workspace uses the
fixed UUID `00000000-0000-4000-8000-000000000000`, has no root directory and
cannot be renamed or deleted.

Version 0.11.0 does not add file, Git, terminal or directory-tree tools. A
Workspace path in the System Prompt is context only; the Agent can act on it
only through a tool that is actually present in that Run's registry.

## Catalog and root policy

`AppPaths` owns `.opensprite/config/workspaces.json`. The strict schema-v1 file
stores the catalog revision, global `activeWorkspaceId`, and at most 100 user
Workspace records with UUID, NFC-normalized name, canonical root, item revision
and UTC timestamps. A missing file exposes only the virtual unassigned
Workspace and creates no directory. The first mutation uses the existing
owner-only, fsynced atomic-replacement boundary; malformed, duplicate-key,
oversized or failed writes fail closed without replacing the last valid file.

Names are 1-80 characters after NFC normalization and trimming, contain no
control characters, and are unique by case-folded comparison. Roots must be
absolute, exist, be readable searchable directories, and resolve successfully.
Filesystem roots, the exact user home, `.opensprite` and its descendants, the
known OpenSprite install root and its descendants, and roots that are symlinks,
junctions or reparse points are rejected. Canonical roots are unique using the
host platform's path-comparison rules; nested legitimate Workspaces remain
allowed.

A saved root that later disappears, becomes inaccessible, stops being a
directory or becomes unsafe is reported as `unavailable` with a bounded reason
code. The catalog never silently substitutes another path.

## SQLite identity and consistency

SQLite schema v12 stores Workspace identity but never a complete root path:

- `conversations`: non-null `workspace_id` and optimistic `revision`;
- `runs`: Workspace ID, Workspace revision, name snapshot and nullable SHA-256
  root hash; and
- `schedules`: non-null `workspace_id`.

The v11-to-v12 transaction assigns every existing Conversation, Run and
Schedule to the unassigned Workspace and creates Workspace-scoped list,
schedule and active-Run indexes. The config catalog intentionally is not an SQL
foreign-key target. `WorkspaceCatalogService`, the Conversation repository and
Schedule service coordinate cross-store mutations through one process-local
`WorkspaceMutationGate` under the single-backend-process deployment rule.

Workspace deletion succeeds only when Conversation, Schedule and active-Run
counts are all zero. Deleting the selected empty Workspace atomically selects
the unassigned Workspace. Changing a root is blocked while the Workspace has an
active Run. No Workspace mutation cascades into Messages, historical Runs,
compactions or user directories.

## Conversation, Run and Schedule behavior

Conversation pagination always receives a Workspace ID. A deep-linked
Conversation can first be queried by ID so the browser can activate its owning
Workspace before loading the scoped list. A normal Conversation may move when
it has no queued, running or cancelling Run; moving increments its revision and
does not rewrite its Messages, Runs or compactions. Schedule-owned
Conversations move only through the Schedule Workspace update transaction.

Before accepting a Run, the chat service resolves one immutable
`WorkspaceExecutionContext`: ID, name, revision, canonical root, root hash,
availability and safe reason. The same object is passed through retries,
compaction, continuation and tool rounds. SQLite, ordinary runtime logs, Run
events and tool receipts receive only the ID, revision, status/name where
contracted and root hash; they never receive the absolute root.

The dynamic System Prompt version 2 contains a delimited, JSON-encoded
Workspace section. Name and root are explicitly untrusted metadata, and the
Prompt states that path knowledge grants no capability. The existing complete
System Prompt log intentionally contains that path and therefore remains
sensitive. An unavailable root does not block a text-only Run; a future
path-dependent tool must inspect the snapshot and fail closed.

A Schedule stores its own Workspace ID at create or edit time and never reads
the global active selection when executing. Changing a Schedule Workspace
atomically moves its dedicated Conversation when no occurrence or Run is
active. Each occurrence resolves the stored Workspace into the same immutable
Run snapshot used by interactive chat.

## Frontend ownership

The application loads the catalog once when the authenticated App mounts. The
active Workspace is backend-owned; it is not copied to localStorage,
sessionStorage, the URL or a polling channel. The Sidebar switcher updates the
catalog and navigates the current tab to `#new-chat`; other open tabs observe
the change on their next reload.

Conversation navigation is scoped to the selected Workspace. Settings owns
Workspace create, rename, controlled root replacement and empty deletion;
desktop uses a Modal and the 390 px layout uses a full-width Drawer. Both native
directory selection and manual paths go through the same backend validation.
The Schedule editor sends an explicit Workspace ID. Unavailable state appears
in the Sidebar, Settings, composer and Schedule UI without disabling plain text
chat.

## Deliberate exclusions

Version 0.11.0 does not include filesystem browsing or mutation, shell or Git
access, per-Workspace model settings, Skills, LINE or another channel adapter,
cross-tab live synchronization, or automatic relocation of missing roots.
