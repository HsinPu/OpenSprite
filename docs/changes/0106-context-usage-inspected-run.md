# Context usage for inspected Runs

## Objective

Show the Context usage belonging to the Run currently displayed in the
workspace, including a historical execution selected for inspection.

## Changes

- Derive the usage event source from the displayed Run: live chat events for
  the latest Run and inspection events for a historical Run.
- Match the usage Provider and model to the displayed Run instead of the
  current composer selection.
- Use the inspected model capability for a conservative fallback limit and
  follow the displayed event stream for compaction status.
- Keep the backend calculation, SSE contract, and stored event payloads
  unchanged.

## Verification

- ChatWorkspace regression test covers a historical Run with a different model
  and Context usage event.
