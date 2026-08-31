# Clear history selection on close

## Objective

Keep the conversation's history-inspection state consistent when the desktop
execution panel is closed from the header.

## Changes

- When a historical execution panel is closed from the header, return to the
  latest Run through the existing inspection controller.
- Clear the selected message's `正在查看` state together with the hidden panel.
- Preserve ordinary panel collapse/expand behavior for the current Run.

## Public impact

No backend, database, HTTP, SSE or Context contract changes. This only joins two
existing frontend state transitions so a closed panel cannot leave a stale
historical selection indicator.

## Verification

- Browser reproduction confirmed the selected history button stayed active after
  closing the panel before this fix.
- ChatWorkspace regression test verifies the close handler calls
  `returnToLatest` while the panel becomes collapsed.
- ChatWorkspace test suite and TypeScript typecheck pass after the fix.

## Remaining work

Mobile Drawer close behavior remains unchanged; its existing history toolbar can
still explicitly return to the latest Run.
