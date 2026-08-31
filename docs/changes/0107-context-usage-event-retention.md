# Context usage event retention

## Objective

Keep Context usage visible for long Runs even though the execution event list
is bounded to the most recent 500 events.

## Changes

- Move Context usage parsing into a focused feature module.
- Keep the most recent valid `model.started` event when trimming the visible
  event list, while retaining the 500-event memory bound.
- Use the same retention behavior for live chat and historical Run inspection.
- Preserve the existing `—` state when no valid Context fields exist.

## Verification

- Context usage unit test covers a full event window and latest-event retention.
- Historical ChatWorkspace, live Run, and inspection hook tests pass.
