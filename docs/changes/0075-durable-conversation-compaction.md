# 0075 — Durable conversation compaction

## Outcome

- Upgraded the current chat database from schema v1 to v2.
- Snapshotted the selected Context budget on every new Run without changing the
  public Run HTTP payload.
- Added append-only `conversation_compactions` records with monotonic sequence
  coverage, source hashes, model provenance and token usage.
- Added a compaction service that treats source messages as untrusted history,
  validates generated summaries and persists only sanitized summary data.
- Raw conversation messages remain untouched and can rebuild every summary.

## Upgrade boundary

Only the immediately previous schema v1 is upgraded. Unknown versions and
malformed databases continue to fail closed. Existing Runs receive the `auto`
Context policy, and no archived OpenSprite database format is imported.

## Verification

- Fresh schema and v1-to-v2 upgrade.
- Run Context budget persistence.
- Compaction monotonicity, source hashing, prompt boundaries and summary
  validation.
- Original-message retention after compaction writes.
