# Managed Workspace mounts interface

## Objective

Expose managed Workspace creation, explicit directory import and external mount
permissions through the existing Settings experience.

## Changes

- Updated the strict frontend Workspace client for managed roots, import pages,
  mount CRUD and the expanded error union.
- Replaced root-path entry during Workspace creation with automatic managed-root
  creation and display-only rename.
- Added existing-directory import plus mount add/edit/enable/disable/remove UI,
  read-only defaults, availability labels and active-Run disabled states.
- Updated the Sidebar, Schedule UI, Run parser and three locale catalogs for the
  fixed Default Workspace and mount-manifest contract.

## Public impact

Users can manage Workspace directory authority without being told that file
tools already exist. Desktop uses modal editors and the narrow layout uses
full-width drawers.

## Verification

- Frontend Vitest: `277 passed`; focused Workspace, Schedule, App and Agent
  tests passed.
- TypeScript typecheck and production build passed.

## Remaining work

- No push or local installed-computer update is included.
