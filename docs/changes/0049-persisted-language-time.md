# 0049 Persisted language and time

## Objective

Replace the demo language and time-zone controls with confirmed, persisted General settings.

## Changes

- Added a strict General settings frontend API client and one state owner that hydrates and saves confirmed values.
- Applied saved locale to React translations, Ant Design and `document.lang` only after successful reads or writes.
- Removed demo time-zone state and used the confirmed time zone for Today grouping and Execution timestamps.
- Kept UTC transport and database timestamps unchanged; locale defaults control date and 12/24-hour presentation.
- Extended frontend architecture guards and localization documentation.

## Public impact

Language and time-zone choices now survive restart through the additive General Settings API. No browser storage or URL state is introduced.

## Verification

- Frontend API, persistence, localization, time-zone boundary, settings, Chat and architecture tests passed.
- TypeScript and production build passed.

## Remaining work

- Other General settings remain session-only demos.
