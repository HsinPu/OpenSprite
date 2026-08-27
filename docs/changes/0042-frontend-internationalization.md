# Frontend internationalization

## Objective

Replace the session-only fake language selector with a typed, working frontend
localization boundary while keeping backend contracts and persistence unchanged.

## Changes

- Added complete Traditional Chinese, English and Japanese message catalogs
  with compile-time key parity and bounded interpolation.
- Added a React locale context, Traditional Chinese fallback, document `lang`
  synchronization and Ant Design locale mapping.
- Localized the application shell, chat workspace, execution context, settings,
  Provider workflow and stable frontend API errors.
- Replaced translated timezone and send-mode state with stable identifiers.
- Replaced title-derived settings-card ids with React-generated ids so English
  headings retain valid accessible names.
- Added localization architecture documentation and focused tests.

## Public impact

The existing language selector now changes the interface between `zh-TW`, `en`
and `ja` for the current browser session. HTTP/SSE payloads, Provider IDs, model
IDs, database schemas, credentials and `.opensprite` files are unchanged.

## Verification

- `npm test -- --run`: 80 tests passed.
- `npm run typecheck`
- `npm run build`
- Browser verification switched the live General settings and main workspace
  through English, Japanese and back to Traditional Chinese.
- Search confirmed user-facing CJK literals remain only in locale resources and
  locale display labels.
- `git diff --check`

## Remaining work

- Locale remains intentionally session-only until a separate General settings
  persistence contract is approved.
- Linux and Windows installer localization remains outside the current frontend
  boundary.
