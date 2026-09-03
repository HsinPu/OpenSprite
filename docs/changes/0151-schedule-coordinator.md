# Scheduled Agent execution

## Objective

Execute durable schedule occurrences through the existing Agent run owner while
preserving restart recovery, non-overlap, and tool-approval safety boundaries.

## Changes

- Added a single-owner coordinator that processes durable pending occurrences
  in scheduled-time order and stops cleanly with the backend runtime.
- Added 15-minute latest-occurrence catch-up, collapsed missed history, per-
  schedule overlap skips, and one-time schedule completion.
- Added an internal Agent chat boundary that applies the saved execution profile,
  marks Runs as schedule-sourced, and always disables full Prompt logging.
- Scheduled Runs now fail with `scheduled_tool_approval_required` when a tool
  would need human approval; no approval request is created or accepted.
- Moved schedule service database operations off the asyncio event loop.

## Public impact

This slice adds execution behavior but does not expose schedule HTTP routes yet.
Existing user-created Runs keep their previous behavior.

## Verification

- Coordinator tests cover service wake-up, dedicated conversation binding,
  one-time completion, collapsed missed occurrences, overlap skipping, and clean
  task shutdown.
- Agent-loop tests prove scheduled write tools fail closed without an approval
  event.
- Existing Agent chat, loop, tool registry, recurrence, and repository tests
  remain green.

## Remaining work

Runtime wiring, strict HTTP contracts, frontend management UI, installer
continuity reporting, versioning, and full verification remain separate slices.
