# Frontend feature ownership

## Objective

Reduce application-shell and settings-page responsibility without changing the
rendered interface, API behavior or persisted settings flow.

## Changes

- Moved conversation-list loading, error handling, refresh and optimistic first
  conversation insertion into `features/chat/useConversations.ts`.
- Moved confirmed AI settings loading, serialized saving, fallback and Provider
  catalog state into `features/settings/useAiSettings.ts`.
- Moved general preference types and defaults into `settingsState.ts`.
- Extracted the General settings section and feature-local visual primitives
  from `SettingsPage.tsx`.
- Added one shared `ModelChoice` feature type used by the application shell,
  settings and chat workspace.
- Updated frontend ownership documentation.

## Public impact

None. Visible copy, interaction, HTTP requests, SSE behavior, model fallback,
focus behavior and session-only general preferences are unchanged.

## Verification

- `npm test -- --run`: 78 tests passed.
- `npm run typecheck`
- `npm run build`
- `git diff --check`

## Remaining work

- Add the approved typed i18n boundary and real locale switching.
- `ModelsSettings` remains one cohesive Provider/model workflow and may be split
  only when a new independent settings capability requires it.
