# Sidebar action order

## Objective

Place the new-conversation action before the Workspace selector in the shared
desktop and mobile navigation sidebar.

## Changes

- Moved the existing new-conversation button above the Workspace switcher.
- Reassigned the existing spacing so the two controls remain visually separated
  without increasing the gap before conversation history.
- Added a DOM-order regression test for the sidebar controls.

## Public impact

The sidebar now presents the primary new-conversation action before Workspace
selection. Button behavior, Workspace state and navigation contracts are
unchanged.

## Verification

- Frontend Vitest: `274 passed`, including the sidebar DOM-order regression.
- TypeScript typecheck and production build passed.

## Remaining work

- No version bump, commit, push or installed-computer update is included.
