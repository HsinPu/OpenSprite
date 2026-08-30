# 0087 — Output-limit completions

## Objective

Preserve useful model text when a Provider reaches its output-token limit,
without weakening malformed-response or incomplete-tool fail-closed behavior.

## Changes

- Added the normalized `OUTPUT_LIMIT` model finish reason for OpenRouter
  `length`, OpenAI incomplete max-token responses, and Anthropic `max_tokens`
  or `model_context_window_exceeded`.
- Completed output-limited Runs with a durable assistant Message when bounded
  non-empty text exists and no tool call is incomplete.
- Added SQLite schema v4 `completion_reason` persistence and migrated existing
  completed Runs plus `run.completed` events to `stop` without rewriting raw
  Messages.
- Added required `completionReason` fields to Run snapshots and completion
  events across the OpenAPI, backend serializer and strict frontend parser.
- Displayed an output-limit notice below the persisted Markdown response and
  an explicit non-error status in current and historical execution details.
- Added Traditional Chinese, English and Japanese UI text.

## Verification

- Provider adapter, Agent Loop, SQLite migration, API contract and frontend
  interaction tests passed.
- Full backend pytest, compileall, offline lock and dependency checks passed.
- Full frontend Vitest, TypeScript typecheck and Vite production build passed.
- A schema-v3 online backup of the installed database upgraded to schema v4
  with table counts preserved and SQLite integrity checks passing; the backup
  was removed after verification.
- `git diff --check` and final worktree inspection passed.

## Public impact

`RunSnapshot` and `run.completed` now require `completionReason`, with values
`stop` or `output_limit`. Message content remains original Markdown. Existing
failed Runs are not rewritten; existing completed Runs migrate to `stop`.

## Deferred

Automatic continuation, a dedicated Continue button and configurable output
token limits remain separate future work.
