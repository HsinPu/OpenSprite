# 0080 — Mobile execution Drawer

## Objective

Keep the mobile chat surface focused by moving the full execution panel out of
the document flow while preserving the desktop side panel.

## Changes

- Added a mobile-only header action that opens the current or inspected Run in
  an Ant Design right-side Drawer.
- Reused `ExecutionContext` in a non-collapsible Drawer mode so the Drawer is
  the only mobile disclosure control.
- Hid the desktop execution sidebar at the mobile breakpoint instead of
  stacking it below the composer.
- Added localized labels, focus restoration, Escape and mask closing behavior,
  independent Drawer scrolling and a bounded mobile width.

## Public impact

HTTP, SSE, SQLite and Context contracts are unchanged. Desktop execution-panel
preference behavior is unchanged; mobile starts closed and does not persist
Drawer state.

## Verification

- Frontend: 17 test files and 145 tests passed.
- TypeScript typecheck and Vite production build passed.
- At the mobile breakpoint the inline execution panel is removed from layout;
  the chat document remains at its original height and the Drawer is 420px wide
  with its own scroll container.
- Escape closes the Drawer and restores focus to the header action.
- At desktop width the right execution sidebar remains visible and the mobile
  action is hidden.
- No backend or API files changed.

## Remaining work

The installed desktop runtime will receive this frontend change on the next
Windows installer update. The current Vite build retains its existing chunk-size
warning, unrelated to this layout change.
