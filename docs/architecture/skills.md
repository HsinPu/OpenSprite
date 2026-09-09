# Global and Workspace Skills

## Storage and policy

AppPaths owns global `skills/<directory>/SKILL.md`, `config/skills.json`, the
recoverable `config/skills-transaction.json` journal and `archive/skills` under
`.opensprite`. Workspace skills live under its managed root, resolved through
Workspace service, never a browser-supplied path. Only first-level SKILL.md is
read: no references, scripts, remote resources or external mounts.

Strict version 3 catalog UUIDs are stable; catalog revision is the optimistic
concurrency token for every mutation. Item revision is audit metadata. Each scope
has no fixed Skill-count cap. Safe YAML requires name and description, permits additional metadata, rejects aliases and duplicate fields, and
invalid UTF-8, bounded to 64 KiB. NFC names are case-insensitively unique within
a scope. Cross-scope names keep distinct IDs but workspace registrations shadow globals.

Effective means master enabled, record enabled, correct Workspace scope, no
same-name workspace registration shadowing it, and a safe/readable valid file.
One resolver reads each relevant file once for list responses and Run snapshots.
Names use NFC plus casefold. Invalid files retain their catalog name for shadowing;
valid external names are used immediately. Same-scope name collisions disable all
colliding candidates. Disabled, invalid or missing workspace Skills never fall back
to globals; deleting the registration restores inheritance for future Runs.
Responses expose shadowed_by_workspace and nullable shadowedBySkillId; ambiguous
workspace collisions have no single shadowing ID. Global lists without workspaceId
show global availability, while workspaceId gives contextual inheritance status.
Newly saved/imported Skills are enabled. Editing via API preserves the existing
toggle; newly scanned valid files are enabled, while invalid files remain disabled.
Rescanning never resets an existing registration's toggle. Valid external edits apply on the
next Run without confirmation. Hashes identify snapshots, not approval gates.
Catalog v1/v2 is atomically migrated to v3, preserving explicit enabled states and
removing disabledWorkspaces. Previously blocked globals become inherited. Legacy
models are accepted only when reading old catalogs or unfinished journals; v3 and
the HTTP response reject the removed field. The workspace-override route is removed.
Legacy confirmedHash remains readable as inert metadata, never an access check.
The enabled HTTP request accepts only enabled and expectedRevision.
Corrupt catalogs fail closed for Skills while ordinary unselected chat remains
available. Invalid manual selections reject Run acceptance.

## Recovery and deletion

Version 0.15.0 replaces folder selection with ZIP import at
`POST /api/skills/import-zip`; the folder HTTP endpoint is removed.
Multipart contains exactly a strict JSON manifest (scope, workspaceId,
directoryName, expectedRevision) and one archive. The ZIP is capped at 12 MiB,
metadata at 1 MiB, with 64 KiB request framing allowance. Uploads remain in
bounded memory, not OS temporary files. Browser preview is local and uses
bounded streaming decompression; confirmation sends the original ZIP.
The backend independently validates paths, entry types, CRCs and quotas,
accepting only stored/deflated, unencrypted archives and one optional wrapper.
No extract-all operation or source filename determines a filesystem target.

Package payload is at most 10 MiB, entrypoint 64 KiB, path depth 8 and each
segment 80 characters. NFC spelling and casefold collisions fail closed;
dependency/VCS directories and nested SKILL.md are rejected. ZIP link entries
are rejected. Destination ancestors and files reject
links/reparse points; only regular bytes are written, never executed.

Transaction journal v2 contains bounded base64 file bytes plus the Skill
record and next catalog. Recovery writes a `.skill-import-<UUID>` sibling stage,
verifies the complete tree, renames to an absent target, then replaces catalog.
After a crash, an already-renamed target must exactly match journal contents;
recovery never overwrites it. Journal v1 remains supported for existing edits
and archive operations. Windows package disk operations use extended-length
paths without changing catalog paths or skipping link/reparse checks.
Before publication, write failures move the stage into
`archive/skills/failed-import-<UUID>-<UUID>/payload` and move the journal beside
it as `transaction.json`. No files are deleted, the catalog remains unchanged,
and a later request can retry without blocking existing Skills. Once the target
has been published, its journal remains recoverable; a mismatching target or
inaccessible archive/catalog still fails closed rather than discarding evidence.
Catalog revision serializes retries: duplicate submissions are rejected with
revision conflict rather than creating another Skill. Cancellation during disk
commit keeps the Workspace mutation gate until the worker finishes.

Directory import preserves the selected root name independently of the YAML
display name. Supporting bytes are retained, but snapshot loading and content
hashes remain SKILL.md-only. They confer no additional execution capability.
UTF-8 BOM is accepted at the start of SKILL.md during parsing; original bytes
and their SHA-256 remain unchanged. Duplicate manifest keys return a non-retryable
400 invalid_request, never a persisted-catalog 503 error.

File/catalog mutations persist a journal first. Recovery rolls forward a
validated file write or archive rename before catalog replacement; failure keeps
recovery state. Archive deletion tolerates already-missing directories. No user
directory is permanently deleted. Workspace removal revokes registration first;
if the later Workspace catalog write fails, retained files need rescan and
explicit enabling. This prefers revocation over retaining enabled instructions.

## Run and Context

Lock order is Workspace mutation gate then Skills RLock. Chat and schedules
capture a frozen SkillExecutionSnapshot and pass it through RunManager to
AgentLoop. Bodies reside in memory but initially only the available count and
discovery instructions enter Context. `discover_skills` searches names/descriptions
within that snapshot or browses with an empty query. Pages contain up to 20 entries
and a next offset. Description previews are limited to 512 characters, explicitly
marked when truncated; full descriptions remain searchable. The browser composer
uses automatic selection only. The optional
API skillIds field still preloads at most five and affects idempotency for API
compatibility; historical manually selected Skill events remain readable.

Internal discovery/load_skill are separate from business-tool policy; loading accepts only a
snapshot ID. Full instructions enter one JSON system-prompt projection; the tool
result confirms loading without duplicating text. Duplicate loads are idempotent.
A candidate exceeding five Skills or input budget is rejected without replacing
the accepted projection. Metadata, definitions and bodies all count toward the
budget. Compaction, continuation and tool rounds reuse the accepted version.
New Runs start fresh; summaries must not perpetuate previous activation.

Skills are untrusted user guidance, not system authority. They cannot grant file
capabilities, enable tools or waive approvals. Scheduled Runs preserve their
no-human-approval rule and use their own Workspace. Models declaring no tool-call
support retain manual selection only.

## API and audit

See `contracts/skills.openapi.json` and `contracts/agent-chat.openapi.json`.
Existing authentication/Origin/Host protection applies. SQLite schema 14 only
widens the event CHECK constraint; no Skills table or body persistence is added.
skill.loaded / skill.load_failed retain ID, revision, hash, source and safe codes.
Unknown IDs use null identity fields instead of echoing untrusted arguments.
Ordinary logs/events omit bodies and paths. Full Prompt logging follows existing
user policy and can contain actual sent instructions.

## Verification boundary

Management lists render 20 rows per own/inherited page. Batch actions still cover
the complete scope, not just the page. HTTP responses remain complete; this is a
DOM optimization, not network pagination. Scan uses name/directory sets to avoid
repeated linear membership checks. Discovery responses count toward Context budget.

Deterministic tests prove projection, idempotency and limits, not model routing.
From backend, `uv run python ../scripts/verify_skills_live.py` runs positive,
near-match and negative probes using an isolated database/current provider.
The 2026-09-06 attempt received Provider HTTP 401 for all three cases. Valid
credentials and a rerun are required before claiming real-model success.
# Bulk operations

`POST /api/skills/batch` uses the Workspace gate then Skills lock and catalog
expectedRevision. Enable and disable persist one catalog replacement. Archive
uses a strict version-3 journal with one scope and canonical archive UUIDs;
recovery completes all recorded renames before removing registrations. Partial
preflight failures remain registered and are reported. Runtime I/O interruption
leaves the journal for roll-forward recovery and returns a storage error.
The master switch and inherited globals are not modified. Existing Run snapshots
remain immutable. UI confirmation freezes scope, count and revision.
