# 0061 Show implemented settings only

## Objective

Make the Settings dialog describe the product that exists today instead of
advertising disabled categories and session-only preferences.

## Changes

- Reduced Settings navigation to General and AI models.
- Removed demo startup, restore, send-mode, notification and speculative model
  preferences together with their transient state and unused icons/copy.
- Renamed the General card to Language and time and the time-zone field to Time
  zone in all three locales.
- Hid the initial saved indicator; saving appears during persistence, completed
  status remains for two seconds, then disappears.
- Tightened header, navigation, content, card and row spacing; widened the form
  surface and added subtle scrollbars.
- Used a compact dialog height for General while retaining the taller,
  independently scrolling AI models surface.

## Public impact

General Settings, AI Settings, Provider and Agent Chat HTTP contracts are
unchanged. Persisted language, time zone, provider, model and response-mode
behavior remains available. No replacement state or compatibility path is
added for removed demo controls.

## Verification

- Settings and localization component tests.
- Complete frontend tests, TypeScript typecheck and production build.
- Desktop and 390px browser checks for hierarchy, overflow, navigation and
  save-status behavior.
