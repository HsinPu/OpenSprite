# Global and Workspace Skills

## Storage and policy

AppPaths owns global `skills/<directory>/SKILL.md`, `config/skills.json`, the
recoverable `config/skills-transaction.json` journal and `archive/skills` under
`.opensprite`. Workspace skills live under its managed root, resolved through
Workspace service, never a browser-supplied path. Only first-level SKILL.md is
read: no references, scripts, remote resources or external mounts.

Strict version 1 catalog UUIDs are stable; catalog revision is the optimistic
concurrency token for every mutation. Item revision is audit metadata. Each scope
allows 100 entries. Safe YAML rejects aliases, duplicate/unknown fields and
invalid UTF-8, bounded to 64 KiB. NFC names are case-insensitively unique within
a scope. Cross-scope names remain distinct IDs without shadowing.

Effective means master enabled, record enabled, correct Workspace scope, no
global override disabling it, safe/readable file and exact approved SHA-256.
New/edited/scanned content never implicitly enables. External edits are pending.
Corrupt catalogs fail closed for Skills while ordinary unselected chat remains
available. Invalid manual selections reject Run acceptance.

## Recovery and deletion

File/catalog mutations persist a journal first. Recovery rolls forward a
validated file write or archive rename before catalog replacement; failure keeps
recovery state. Archive deletion tolerates already-missing directories. No user
directory is permanently deleted. Workspace removal revokes registration first;
if the later Workspace catalog write fails, retained files need rescan and
reconfirmation. This prefers revocation over retaining enabled instructions.

## Run and Context

Lock order is Workspace mutation gate then Skills RLock. Chat and schedules
capture a frozen SkillExecutionSnapshot and pass it through RunManager to
AgentLoop. Bodies reside in memory but initially only ID/name/description/scope
enter Context. Manual skillIds preload at most five and affect idempotency.

Internal load_skill is separate from business-tool policy and accepts only a
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

Deterministic tests prove projection, idempotency and limits, not model routing.
From backend, `uv run python ../scripts/verify_skills_live.py` runs positive,
near-match and negative probes using an isolated database/current provider.
The 2026-09-06 attempt received Provider HTTP 401 for all three cases. Valid
credentials and a rerun are required before claiming real-model success.
