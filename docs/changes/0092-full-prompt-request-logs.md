# 0092 — Full model request logs

## Objective

Allow deliberate local debugging of the exact provider-neutral conversation sent
for a model request while keeping ordinary runtime logs free of prompts.

## Changes

- Added opt-in `logFullPrompts`, disabled by default and snapshotted per Run.
- Added immutable request receipts under `.opensprite/logs/prompts/<date>/<run>`
  for main and continuation model calls.
- Recorded System Prompt, user message and all included context in request order;
  model output and credentials remain excluded.
- Added the setting to the strict AI Settings contract and to each Run snapshot,
  so a setting change cannot alter an already-running request.
- Added atomic owner-protected writes, bounded receipt size and strict settings/
  SQLite migrations without changing the chat response payload.

## Safety

Prompt receipts are plaintext and may contain sensitive user-provided content.
They remain local only, use the existing profile ACL boundary and are not shown
through the HTTP API or the normal backend log.
