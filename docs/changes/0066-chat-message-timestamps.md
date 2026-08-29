# 0066 Chat message timestamps

## Objective

Show a quiet, localized time directly beneath every chat message without
changing message persistence or the Agent loop.

## Changes

- Added a message-specific hour-and-minute formatter that follows the confirmed
  locale and time-zone settings while preserving the existing execution-time
  formatter with seconds.
- Rendered semantic `time` elements beneath persisted and optimistic user
  messages, persisted assistant messages and the active streaming response.
- Aligned user timestamps to the right and assistant timestamps to the left,
  using the existing muted color and responsive message widths.
- Kept the authoritative UTC `createdAt` value in each `datetime` attribute and
  introduced no API, database or browser-storage change.

## Verification

- Focused timestamp formatting and ChatWorkspace component tests passed.
- Full frontend verification passed: 13 test files and 114 tests, TypeScript
  typecheck and the Vite production build.
- Desktop and narrow browser checks showed timestamps under both message roles,
  no horizontal overflow and no console errors.
