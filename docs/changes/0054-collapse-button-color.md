# 0054 Collapse button color

## Objective

Match the default visual weight of the left and right shell collapse controls.

## Changes

- Changed the Execution collapse button from the primary chat text color to the shared muted color used by the sidebar control.
- Preserved the orange hover state, dimensions, icons and behavior.

## Public impact

Both collapse controls now use the same default gray and orange hover treatment. No functional behavior changed.

## Verification

- Browser measurement confirmed both controls compute to `rgb(111, 114, 120)` while main chat text remains `rgb(32, 33, 36)`.
- All 93 frontend tests, TypeScript checks and the production build passed.

## Remaining work

- None for the collapse-control color mismatch.
