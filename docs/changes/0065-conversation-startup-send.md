# 0065 Conversation startup and send behavior

## Objective

Make the persisted conversation settings control actual startup navigation and
composer keyboard behavior without changing explicit URLs or the send button.

## Changes

- Added one frontend conversation-settings controller and wired it into the App
  and General settings view.
- Replaced the three startup/send roadmap rows with two persisted selectors;
  notifications remain visibly marked as a future feature.
- Applied startup navigation once per application mount after settings and the
  conversation list load. Valid `#chat=<uuid>` and `#new-chat` URLs always win.
- Added the `recent` fallback to the first recently updated conversation, with
  safe fallback to `#new-chat` when no conversation exists or settings fail.
- Added IME-safe composer keyboard handling for Enter or Ctrl/Cmd+Enter modes.
- Added Traditional Chinese, English and Japanese labels for the new controls.

## Verification

- Frontend focused startup, Settings and composer tests passed.
- Full frontend verification passed: 13 files and 112 tests, TypeScript and the
  Vite production build.
- Full backend verification passed: 386 tests, with two platform-specific
  skips, plus compileall, offline lock and dependency checks.
- Live backend smoke returned `ok` and the confirmed `new` plus `enter`
  settings. Desktop and narrow browser checks showed both selectors, one
  remaining future badge, no horizontal overflow and no console errors.
