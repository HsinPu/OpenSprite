# 0077 — Execution panel preference

## Outcome

- The outer current-execution panel now defaults to collapsed on desktop and
  mobile.
- General Settings exposes a persisted "Expand execution details by default"
  switch below chat auto-scroll.
- Manual disclosure remains local to the mounted Conversation and does not
  write settings or reset during Run/event updates.
- Historical Run inspection still expands automatically; returning to the
  latest Run restores the confirmed default.

## Contract and persistence

- Added required boolean `executionPanelDefaultExpanded` to the existing
  Conversation Settings HTTP resource.
- Upgraded `config/conversation.json` to strict schema v3 with a default of
  `false`.
- Current schema v2 is read as `false` without a read-time write; the next
  successful PUT writes canonical v3. Schema v1 remains unsupported.
- No new endpoint, data root, browser storage, database table, or installer
  behavior was introduced.

## Verification

- Backend default, v2 normalization, strict schema, atomic write, API and
  OpenAPI tests.
- Frontend API, settings save/error, disclosure state, historical inspection,
  accessibility, typecheck and production build.
- Full backend/frontend suites, Windows installer isolation test, desktop and
  390px browser checks, and repository hygiene checks.
