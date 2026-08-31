# Output continuation policy

## Objective

Replace the fixed boolean automatic-continuation behavior with a Run-snapshotted
policy supporting off, 1, 2, 3, 5, or unlimited continuation attempts.

## Changes

- Replace `autoContinueOutput` with strict `outputContinuation` settings.
- Read AI-settings schema v6 booleans as `2` or `off`; write only schema v7.
- Replace the Run boolean with a strict SQLite text snapshot in schema v8.
- Rebuild the Run table transactionally while preserving Messages, Runs,
  compactions and Run events.
- Execute limited policies exactly as configured and bound unlimited mode to 64
  continuation requests plus existing cancellation, Context and output guards.
- Allow `response.continuation.started.maxAttempts` to be null for unlimited
  mode while preserving old numeric events.
- Update backend/OpenAPI validation and frontend parsers for the new contract.

## Public impact

`GET/PUT /api/settings/ai` now uses `outputContinuation` with values `off`, `1`,
`2`, `3`, `5`, or `unlimited`. Existing local schema-v6 settings and schema-v7
databases upgrade automatically; no raw conversation content is rewritten.

## Verification

- Backend tests cover setting conversion, strict payloads, SQLite migration,
  configured attempt counts, unlimited completion and the 64-attempt safety cap.
- Frontend contract tests accept the new settings and continuation-event shapes.
- Targeted backend and frontend tests plus TypeScript typecheck pass.

## Remaining work

The settings screen still presents the temporary on/off control in this slice;
the following frontend slice replaces it with the full policy selector.
