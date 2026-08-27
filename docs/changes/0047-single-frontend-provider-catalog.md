# 0047 Single frontend Provider catalog

## Objective

Give the frontend one owner for Provider summaries, OpenRouter discovery and derived model choices without changing the settings or chat behavior.

## Changes

- Added `useProviderCatalog` under `features/ai-settings` as the single owner of Provider loading, OpenRouter model discovery, catalog errors, cache invalidation and derived model choices.
- Composed the catalog once in `App` and passed the same controller to AI settings, Chat and Settings consumers.
- Removed the duplicate Provider fetch and model-choice state from `useAiSettings` and `SettingsPage`.
- Preserved per-Provider merge behavior for failed connection-test refreshes so one stale response cannot overwrite another Provider's newer result.
- Added an architecture test that prevents Provider catalog reads from spreading to another frontend feature.

## Public impact

None. UI interactions, HTTP requests, dynamic model behavior, saved AI settings, error text and browser persistence behavior are unchanged.

## Verification

- `npm test -- --run`: 9 files and 82 tests passed.
- `npm run typecheck`: passed.

## Remaining work

- Provider operation feedback and connection modals remain presentation concerns inside Settings.
