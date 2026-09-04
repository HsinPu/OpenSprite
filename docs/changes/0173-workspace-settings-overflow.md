# Workspace settings overflow containment

## Objective

Keep long managed and mounted directory paths inside the Settings content area
at desktop and narrow viewport sizes.

## Changes

- Allowed the Workspace card, summary and mount grids to shrink within their
  parent layout.
- Made the path summary use the available width before applying ellipsis.

## Verification

- Runtime browser inspection confirmed that the Settings content area no
  longer has horizontal overflow with long managed and mounted paths.
- Frontend Vitest, TypeScript typecheck and production build passed.

## Remaining work

- No push or installed-computer update is included.
