# Full-page settings workbench

## Scope

- Replace the native settings dialog with a full-viewport settings surface.
- Keep the chat tree mounted but hidden and inert; preserve drafts, selected
  conversation and existing run controller lifetimes. No route or API changes.
- Restore the opener on return; scheduled-conversation navigation still opens
  the target conversation without reopening the mobile sidebar.
- Keep existing colors, categories and setting controls. Add a 240px desktop
  navigation rail, independent content scrolling and centered content limits
  (960px for General/Privacy/About, 1200px for other settings).
- On narrow screens, use a category Drawer and current-category header.
- Preserve child overlays and their Escape priority. Ignore hidden chat menus
  when deciding whether Escape may leave settings.
- Add Traditional Chinese, English and Japanese return labels; remove unused
  native-dialog/header styles. User-menu decorative icons are hidden from AT.

## Verification

- Full frontend suite: 52 files, 434 tests passed (`--maxWorkers=1`).
- App regression tests cover full-page rendering, return focus, Escape, draft
  DOM preservation, category Drawer selection and schedule navigation.
- Typecheck and production build pass. The pre-existing large-chunk build
  warning remains; no dependency changes were made.
- Browser checks against the Vite preview at localhost:5174: 1920x1080,
  1366x768, 768x900 and 390x844; no horizontal overflow in checked layouts.
- Mobile category selection and provider connection modal were exercised.
  Escape closes the provider modal first, then settings. Desktop return
  preserves a typed, unsent draft and restores focus to the user button.
- Browser viewport override was reset. No provider credentials were changed,
  no paid run was sent, and 200% browser zoom was not separately exercised.
- No release bump, commit or installed-runtime update in this slice.
