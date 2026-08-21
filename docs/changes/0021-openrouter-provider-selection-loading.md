# 0021 OpenRouter provider selection while loading

## Objective

Keep the model-provider control understandable when OpenRouter is the only
connected provider and its dynamic model list is still loading.

## Changes

- Treat the sole connected provider as the active provider while no persisted
  default model exists.
- Keep the model selector disabled with its existing loading message until
  OpenRouter discovery finishes.
- Leave model selection available as soon as discovery returns; no temporary
  model ID, credential write, or new API call is introduced.

## Verification

- Added a SettingsPage regression test for the sole-connected OpenRouter
  loading state and the returned model becoming selectable.
- Frontend unit tests, TypeScript, and production build are recorded with the
  implementation commit.
