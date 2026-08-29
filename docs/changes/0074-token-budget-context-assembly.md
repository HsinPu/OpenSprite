# 0074 — Token-budget context assembly

## Outcome

- Added a provider-neutral Context budget resolver with an 8K response reserve,
  a minimum 4K safety reserve, a 75% compaction trigger and a 55% target.
- Added a conservative local token estimator that includes messages, tool
  definitions, tool calls and tool results.
- Added a pure Context assembler that always retains the configured recent
  message floor, enforces the 256-message model boundary and reports when older
  history needs compaction.
- Required recent context now fails explicitly when it cannot fit; the
  assembler never silently removes it.

## Boundary

This slice does not change the live Agent loop. The existing fixed history path
remains active until durable compaction is available and the integration can be
switched atomically.

## Verification

- Budget resolution across auto, fixed and max choices.
- Tool-aware token estimates.
- Recent-history retention, compaction signaling, overflow failure and ordered
  history validation.
