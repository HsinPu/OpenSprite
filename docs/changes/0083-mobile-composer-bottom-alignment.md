# 0083 — Mobile composer bottom alignment

## Objective

Keep the compact chat composer near the bottom of the available viewport, like
the desktop workspace, while preserving access to long conversations.

## Changes

- Made the compact application shell occupy one dynamic viewport height below
  the fixed 60px application header.
- Gave compact `app-content` a definite `calc(100dvh - 60px)` height instead of
  relying on an unresolved minimum height.
- Made the compact chat workspace and main column fill that available height.
- Restored the conversation region as the internal scroll owner at all compact
  widths, including phones, so the composer remains in the bottom layout row.
- Kept the existing compact composer width, controls and bottom spacing.

## Public impact

No chat, API, persistence, message, auto-scroll or model-selection contracts
changed. Only compact layout height and scroll ownership changed.

## Verification

- Full frontend Vitest passed: 17 test files and 148 tests.
- TypeScript typecheck and Vite production build passed. Vite retained its
  existing bundle-size warning.
- Installed-runtime browser verification covers a short compact conversation,
  internal message-scroll ownership, composer bottom position and desktop
  layout preservation.
- Browser measurements confirmed the compact workspace fills the viewport below
  the 60px header, the composer sits about 17px above the bottom edge and the
  document no longer grows beyond the viewport. Desktop retained its 24px
  composer bottom spacing and internal conversation scrolling.

## Remaining work

- None for this UI slice.
