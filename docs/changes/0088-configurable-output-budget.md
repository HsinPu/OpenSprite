# 0088 — Configurable output budgets

## Objective

Replace the fixed 8K model-response reserve with a user-selectable budget that
stays bounded by the chosen Context window and the selected model capability.

## Changes

- Added `auto`, `8k`, `16k`, `32k`, `64k`, and `max` output choices to the
  atomic model selection.
- Auto uses one quarter of effective Context up to 32K. All choices retain a
  25% input reserve, the existing safety reserve, and the model's maximum.
- OpenRouter aliases without an explicit output capability use the same
  Context-bounded 32K fallback in backend execution and frontend guidance.
- Upgraded AI settings to schema v4; schema-v3 selections load as
  `outputBudget: auto` without a read-time rewrite.
- Upgraded SQLite to schema v5 so each Run snapshots its requested output
  budget. Existing Runs migrate to `auto` and historical model-start events
  receive the former effective 8,192-token limit.
- Persisted the resolved `maxOutputTokens` in `model.started` and displayed it
  in current and historical execution details.
- Added the output selector, disabled infeasible fixed choices, effective-limit
  guidance, and automatic fallback to Auto when a Context change invalidates
  the selected fixed value.
- Added Traditional Chinese, English, and Japanese copy.

## Verification

- Backend and frontend budget matrices passed for Context, model, fixed,
  automatic, and maximum bounds.
- AI settings schema-v3 and SQLite schema-v3 backups upgraded through the new
  versions with settings, table counts, Messages, Runs, and events preserved.
- Full backend pytest, compileall, offline lock, and dependency checks passed.
- Full frontend Vitest, TypeScript typecheck, and production build passed.
- Windows installer isolation and `git diff --check` passed.

## Public impact

AI settings `ModelSelection` now requires `outputBudget`. Agent-chat Run
snapshots remain unchanged, while `model.started` events add the resolved
`maxOutputTokens` integer.

## Deferred

Automatic continuation, arbitrary numeric values, and Provider-specific output
policies remain out of scope.
