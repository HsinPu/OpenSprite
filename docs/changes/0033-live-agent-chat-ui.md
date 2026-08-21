# 0033 — Live Agent chat UI

## Objective

Replace the remaining fake conversation and execution surfaces with the real
Conversation, Run, and SSE workflow without adding any unimplemented tools.

## Changes

- Added a strict frontend client for conversation pages, message pages, Run
  snapshots, cancellation, and named semantic SSE events.
- Added a conversation-run controller that keeps optimistic user input visible,
  reconnects to durable Run events, accumulates assistant text, and reloads the
  authoritative Run and messages at a terminal event. Terminal events close
  SSE and leave the active state immediately, even if that final reload fails.
- Replaced hard-coded sidebar conversations with the backend conversation list;
  URL hashes now contain only backend-generated conversation UUIDs.
- Replaced the fake assistant summary and fake Search/File/Memory capability
  list with persisted messages, live assistant text, actual Run status, actual
  semantic events, and only tools that appeared in those events.
- Added a stop action for active Runs and fixed unavailable attachment/options
  actions as clearly marked future features.

## Verification

- Frontend Agent-chat contract tests cover strict HTTP and SSE parsing.
- Conversation-run hook tests cover persisted loading, streaming completion,
  terminal-refresh failure, and cancellation.
- Workspace tests prove that a real Run is displayed, cancellation is exposed,
  and unregistered tools are not advertised.
- Full frontend Vitest, TypeScript, and production build are required before the
  slice is committed.
