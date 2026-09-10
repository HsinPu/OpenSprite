# General settings layout

## Scope

Reorganize the existing General settings UI without changing API contracts,
stored values, defaults, model settings, or conversation behavior.

## Changes

- Group the six existing controls into Language and time, Conversation
  preferences, and Execution panel.
- Replace native selects with Ant Design selects, keeping stable control IDs,
  accessible names, values, callbacks, and independent saving states.
- Shorten selected send-mode labels and retain the complete keyboard rule in
  associated helper text.
- Explain that the execution panel can still be opened or closed manually.
- Collapse planned desktop notifications and sounds by default. No fake toggle
  or persistence operation is added.
- Keep language/time errors separate from conversation/panel errors. Display
  the shared conversation error once. Label reload explicitly and allow it
  after initial-load failure.
- Preserve the existing palette and 960px content cap. Stack select controls
  when the content container is narrow, including tablet layouts with a rail.
- Add Traditional Chinese, English, and Japanese labels and UI regression tests.

## Verification

- Final full frontend suite: 54 files, 451 tests passed.
- Settings page tests: 36 passed.
- General settings and internationalization tests: 15 passed, including failed
  persistence and rapid controller-save reconciliation. Existing native-select
  interaction tests were updated for Ant Design without changing production
  persistence behavior.
- Typecheck and production build passed. The existing large-chunk warning remains.
- Browser checks at 390, 768, 1366, and 1920 CSS-pixel widths found no horizontal
  settings-content overflow. 768px stacks controls; 1366px aligns them in rows;
  the 1920px view retains a 960px form.
- Escape closed the select only and retained field focus. Planned content had
  no editable control. Returning to chat preserved the unsent test draft; the
  test draft was then cleared. No user preference was changed by browser checks.
- Development hot-update logs contained React root/deletion errors while locale
  files were being edited. A fresh tab repeated settings/select/collapse/return
  interactions with an empty error log.
- Actual browser 200% zoom was not exercised. Viewport overrides were reset.
- No version bump, local installation, commit, or push is part of this slice.
