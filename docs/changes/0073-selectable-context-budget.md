# 0073 — Selectable context budget

## Outcome

- Added `auto`, `32k`, `64k`, `128k`, `256k` and `max` context-use
  choices to each persisted model selection.
- Added the Context limit selector below the model picker with model-aware
  disabled options and an effective-limit summary.
- Added Traditional Chinese, English and Japanese copy for the new control.
- Model changes reset the context policy to `auto` so a large-model choice is
  never carried accidentally to a smaller model.

## Persistence

AI settings use strict schema v3. The immediately previous schema v2 is read
as `contextBudget: auto` without a read-time write; the next confirmed settings
mutation writes canonical v3. No archived or older settings format is accepted.

## Verification

- Backend settings persistence, current-schema upgrade, API and OpenAPI tests.
- Frontend context policy, API boundary, Settings, App and ChatWorkspace tests.
- TypeScript typecheck and production build.
