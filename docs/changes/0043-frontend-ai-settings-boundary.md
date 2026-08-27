# 0043 Frontend AI settings boundary

## Objective

Move shared AI model selection ownership out of the settings presentation feature without changing UI or API behavior.

## Changes

- Added `frontend/src/features/ai-settings` as the owner of the model catalog, model-selection types, persisted AI-settings state and save flow.
- Updated the app shell, chat workspace and settings page to consume that boundary.
- Removed the former model catalog and state hook from `features/settings`.
- Documented the frontend ownership boundary in the architecture overview.

## Public impact

None. HTTP payloads, SSE behavior, browser UI, persisted settings and user-data paths are unchanged.

## Verification

- `npm test -- --run`: 8 files and 80 tests passed.
- `npm run typecheck`: passed.
- Search confirmed no callers use the removed `features/settings/modelCatalog` or `features/settings/useAiSettings` paths.

## Remaining work

- Add an automated frontend import-boundary guard.
- Keep Provider connection UI inside the settings presentation feature until a separate approved workflow needs another owner.
