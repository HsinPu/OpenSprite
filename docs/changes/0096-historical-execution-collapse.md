# Historical execution collapse

## Objective

Allow the desktop execution-details panel to remain manually collapsed while
viewing a historical Run.

## Changes

- Keep the automatic expansion when historical inspection is entered.
- Apply that expansion only on entry instead of on every render.
- Preserve the header toggle state after a user collapses the historical panel.
- Keep returning to the latest Run and the confirmed default preference
  behavior unchanged.

## Public impact

No backend, database, HTTP, SSE or Context contract changes. This is a frontend
state correction for the existing desktop disclosure control.

## Verification

- Added a ChatWorkspace regression test that opens historical execution details,
  collapses them, and verifies `aria-expanded=false` plus the hidden body.
- Existing ChatWorkspace tests continue to pass.
- The local browser reproduction previously showed the effect reopening the
  panel; the new state transition is covered by the regression test.

## Remaining work

No change is made to mobile Drawer behavior or execution-panel preferences.
