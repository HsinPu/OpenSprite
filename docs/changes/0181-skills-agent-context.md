# Skills Agent and Context integration

Run acceptance captures immutable Skill content under the Workspace mutation gate.
Manual selection is included in idempotency. The internal `load_skill` definition
is independent of business-tool enablement. Context initially carries metadata;
selected instructions enter the system projection once, with actual token accounting.
Loaded instructions remain in the Run projection used for continuation/compaction.

SQLite schema 14 expands the existing event constraint to accept `skill.loaded`
and `skill.load_failed`; it adds no Skills table or instruction persistence.
Migration preserves event rows transactionally and rolls back injected failures.

Verification includes deterministic real-loop lazy loading and duplicate loading,
plus existing Agent, chat, repository and runtime regression tests. A deterministic
gateway is not evidence of real-model selection quality.

The API route matrix verifies every Skills operation requires authentication.
Additional checks cover manual first-request injection, five-Skill limits,
missing-file removal, scope isolation and invalid-document discovery.
Workspace removal revokes registration before removing the Workspace catalog
entry. If that later catalog write fails, files remain and a rescan/reconfirmation
is required; a failed operation cannot silently restore enabled instructions.

The live probe uses an isolated database and does not change installed settings.
On 2026-09-06 all three OpenRouter requests returned HTTP 401. Positive,
near-match and negative routing remain unverified until valid credentials are
available. No credentials were changed.
