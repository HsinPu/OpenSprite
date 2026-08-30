# 0081 — Execution controls aligned with shell headers

## Objective

Keep the right execution control visually aligned with the left navigation
control at both desktop and compact widths.

## Changes

- Lifted the desktop execution-panel expansion state to `ChatWorkspace`.
- Kept navigation collapse state in `App` but moved its Ant Design control out
  of the sidebar brand block and into the left side of the desktop chat title
  bar. The execution control remains on the title bar's right side.
- Added an Ant Design icon button beside the desktop chat title. It uses the
  existing localized collapse/expand labels and controls the desktop execution
  body.
- Removed the duplicate collapse control from `ExecutionContext`; the sidebar
  keeps its heading and becomes a narrow, empty rail when collapsed.
- Moved the compact execution action into the far-right action slot of the
  global `OpenSprite` mobile header. The icon-only button opens the existing
  right-side Drawer and restores focus after close.
- Aligned the shell and execution breakpoints at 900px so compact layouts never
  show both the fixed top header and the desktop execution sidebar.
- Kept the compact hamburger menu unchanged; the desktop navigation control is
  hidden with the rest of the desktop title-bar actions at 900px and below.
- Preserved historical Run auto-expansion, the saved default preference, Run
  event rendering and all backend/API behavior.

## Public impact

No HTTP, SSE, SQLite, persistence or model-selection contracts changed. Above
900px the desktop toggle remains in the chat header; at 900px and below the
global top header owns the visible execution action and the Drawer is the only
execution disclosure surface.

## Verification

- Focused ChatWorkspace and ExecutionContext tests cover the header control,
  controlled panel state, historical expansion and Drawer mode.
- Full frontend Vitest passed: 17 test files and 148 tests covering the global
  header portal, compact Drawer, paired desktop title-bar controls and
  navigation isolation.
- TypeScript typecheck and Vite production build passed. Vite retained its
  existing bundle-size warning.
- Installed-runtime browser verification confirmed the 40px compact action is
  inside `.mobile-header-actions`, aligned 16px from the right edge, opens the
  Drawer and receives focus after close. The desktop header control remains
  visible above 900px while the compact action and mobile header are hidden.
- Desktop browser verification confirmed the title-bar order is navigation
  button, heading and execution button; the old sidebar-header button is absent.
  The navigation control collapsed the sidebar from 248px to 76px and restored
  it from the same title-bar position.

## Remaining work

- None for this UI slice.
