# Workspace schedules, tools and Prompt context

## Objective

Carry one immutable Workspace identity through scheduled Runs, System Prompt
construction and structured Tool invocation.

## Changes

- Added explicit Workspace ownership to Schedule requests, records and responses.
- Kept Schedule-owned Conversation movement in the same SQLite transaction and
  blocked changes while an occurrence or Run is active.
- Resolved and verified one Workspace execution context for every Agent Run.
- Added safely delimited Workspace metadata to System Prompt version 2.
- Added Workspace identity, revision and root hash to Run-start events,
  ToolContext and version-2 approval receipts without recording absolute roots.

## Public impact

Schedule create and update requests now require `workspaceId`. Schedule responses
and Run-start events expose non-secret Workspace identity metadata.

## Verification

- Schedule repository, API, coordinator and contract tests.
- Agent loop snapshot, ToolContext, receipt and Prompt log tests.
- Frontend schedule and Agent-event contract tests and TypeScript checks.

## Remaining work

Workspace selection, management, Conversation move controls and localized UI
are not included in this slice.
