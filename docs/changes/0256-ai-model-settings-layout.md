# AI model settings: provider-first layout

## Scope

- Keep the existing palette and the full-page settings shell.
- Order the page as provider connections, default model, response settings,
  collapsed advanced/debugging settings, and collapsed planned features.
- No provider API, credential storage, model reconciliation, run policy,
  version, or local-installation changes.

## Implementation

- Replace nested provider cards with compact rows and separators. Keep connect
  and manage visible; move connection tests and removal into an accessible
  per-provider menu. Removal still requires explicit confirmation.
- Keep provider operation feedback with its row. Show masked credential
  previews only in the connection-management dialog.
- Keep the custom-provider connection row and all existing model-management
  operations. Move refresh, model management, and removal into its menu.
- Keep provider selection, model selection, integrated refresh, and response
  mode together. Group context/output limits, delivery, and continuation in a
  separate response card; keep each limit summary with its control.
- Collapse debugging and planned controls by default. Show the enabled logging
  indicator without requiring expansion. Expansion never saves a setting.
- Use a container breakpoint for stacked controls, including narrow desktop
  content beside the settings rail. Retain the existing content width cap.
- Add Traditional Chinese, English, and Japanese labels and regression checks.
- Restore focus to the provider menu trigger when canceling removal.

## Verification

- Full frontend suite: 52 files, 439 tests passed before the final additional
  localization/custom-provider test cases.
- Final targeted settings/custom-provider suite: 2 files, 39 tests passed.
- Typecheck passed. Production build passed; existing large-chunk warning remains.
- Browser preview against the local development UI and existing backend:
  390, 768, 1366, and 1920 CSS-pixel widths showed no settings-content horizontal
  overflow. 768px uses stacked controls; 1366px uses aligned horizontal rows.
- Verified the visible logging-enabled summary, expanded logging switch without
  changing it, provider menu contents, and removal cancellation with Escape.
  Settings stayed open and focus returned to the provider menu button.
- Browser error log was empty. Browser viewport override was reset.
- No live credentials were changed, no provider was removed, and no model
  request was submitted. Actual browser 200% zoom was not exercised.
- No commit, push, version bump, or local update was performed.
