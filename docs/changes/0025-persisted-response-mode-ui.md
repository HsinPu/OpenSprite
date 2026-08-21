# 0025 - Persisted response mode UI

## Summary

Connected the AI model settings screen to the unified AI settings contract and
made response mode a persisted setting instead of session-only demo data.

## Changes

- Replaced the model-only frontend client with a strict `/api/settings/ai`
  client for model and response mode together.
- Renamed the control from response speed to response mode and mapped the
  Chinese labels to `fast`, `balanced`, and `deep`.
- Hydrated both settings on startup and saved either change as one atomic
  payload; failed writes keep the last confirmed values.
- Removed `DemoSettings.responseSpeed` and the old frontend API module without
  a compatibility alias.
- Kept settings, dynamic model catalogs and credentials out of browser storage,
  URLs and logs.

## Verification

- `npm test -- --run tests/aiSettings.test.ts tests/App.test.tsx tests/SettingsPage.test.tsx`
- Full frontend test, TypeScript and production build checks run before commit.
