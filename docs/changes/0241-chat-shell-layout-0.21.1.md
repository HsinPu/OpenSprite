# 0.21.1 — Chat shell layout

## Scope

- Keep the existing color tokens, authentication, Providers, execution APIs and data layout.
- Replace the desktop narrow collapsed rails with completely hidden left/right panels.
- Keep independent controls at opposite ends of the global top bar, with a compact Workspace / conversation heading and a new-chat action. Remove the duplicate large chat heading.
- Retain the left navigation order and bottom settings entry. Align the conversation rail and composer at an 820px maximum reading width.
- Use overlay navigation/execution panels at 900px and below; preserve drafts and restore focus. The existing explicit execution-panel preference remains supported (default false).
- Keep desktop execution visibility in the shell so accepting a new conversation does not reset the user's panel choice. Run activity does not force panels open. Pending approvals remain actionable inline when the execution panel is hidden.
- Remove two disabled composer placeholder actions; Context and send/stop remain available.

## Verification

- Full frontend suite: 424 tests passed across 50 files; final controlled-panel state refinement also passed 53 focused App/ChatWorkspace tests, including new-conversation acceptance retaining the open panel.
- Typecheck and production build passed. Existing large-chunk warning remains.
- `uv lock --check --offline` and `uv pip check` passed.
- Isolated browser fixture uses the actual App and ChatWorkspace, with deterministic transports and no installed user-data access.
- Browser measured CSS viewports: 390, 768, 1280 and 1920px; no document horizontal overflow. At 1280px both panels hidden give the chat main all 1280px, with no collapsed rails. Desktop independent panel combinations, mobile drawers, draft preservation and focus restoration checked.
- No live model execution or Windows installation update performed. Backend behavior and schema unchanged; full backend/installer suites not rerun for this frontend layout release.

## Delivery

Version 0.21.1; no commit, push or local deployment in this task.
