# Tools settings layout

## Scope

Refine the approved Tools settings layout without changing backend APIs, tool permissions, saved defaults, or MCP execution policy. Preserve the existing palette and settings primitives.

## Changes

- Move the Tools title and global switch into one page header. Show a paused notice without clearing individual tool choices.
- Rename the built-in section and display compact name/source/effect rows; only unavailable tools need a separate availability label.
- Give MCP connections a heading-level add action and a compact list with real status tags. Keep connect/disconnect visible; move edit, test, and remove to the labeled action menu.
- Keep command and endpoint previews in the existing save/start confirmations, not the normal list. Put tool and authentication details behind a disclosure.
- Preserve separate save and start confirmations, add a removal modal, and restore focus to a surviving trigger after closing.
- Collapse advanced autostart and planned features by default. Keep executable arguments and authentication inputs visible because they can be necessary for a valid connection.
- Add Traditional Chinese, English, and Japanese copy, responsive header/list wrapping, and long-content overflow rules.

## Verification

- Focused frontend suites: 48 tests passed (ToolsSettings, McpServersSettings, SettingsPage).
- Typecheck and production build passed. The existing large-bundle warning remains.
- Browser at the development preview: desktop layout at 1138 px, no document overflow, add/cancel form, collapsed advanced settings, and focus returning to Add connection.
- No live MCP process was started and no saved user preferences or connections were changed during browser verification.
- Exact 390/768/1366/1920 viewport and 200% zoom checks were not performed in this slice; responsive CSS is implemented but those visual checks remain unverified.
- Full frontend suite: 55 files, 456 tests passed. `git diff --check` passed. JSDOM emitted its existing pseudo-element getComputedStyle warnings.

## Delivery boundaries

No version bump, local installation, commit, or push in this slice.
