# Expanded output continuation

## Objective

Default new AI settings to five automatic continuation requests and provide
larger bounded choices for long model responses.

## Changes

- Expanded the strict continuation policy to `off`, 1, 2, 3, 5, 10, 20, 50,
  or `unlimited`; unlimited retains the existing 64-request safety cap.
- Changed only the missing-settings default from 2 to 5. Existing settings files
  and persisted Run snapshots retain their saved policy.
- Advanced the conversation database to schema v10 so the strict Run CHECK
  accepts the new finite values without losing existing Runs or events.
- Updated the settings selector, event validation, three locales, and contracts.

## Public impact

`GET /api/settings/ai` returns `outputContinuation: "5"` when no settings file
exists. The PUT contract accepts `"10"`, `"20"`, and `"50"` in addition to the
previous values.

## Verification

Backend suite passed with 602 tests and 2 existing conditional skips. Frontend
Vitest passed with 230 tests; typecheck, production build, offline lock and
dependency checks, and Windows installer isolation also passed.

## Remaining work

Existing saved settings are not automatically changed to five.
