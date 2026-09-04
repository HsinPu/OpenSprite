# Workspace catalog and API

## Objective

Add the strict, atomic local Workspace catalog and its authenticated HTTP boundary.

## Changes

- Added the reserved unassigned Workspace and a versioned `workspaces.json` store.
- Added canonical single-directory validation with high-risk-root rejection.
- Added optimistic Workspace create, read, update, active-selection and empty-delete operations.
- Added strict API models, duplicate-key rejection and an authoritative OpenAPI contract.

## Public impact

The backend now exposes `/api/workspaces` management operations when a Workspace
service is composed. The normal runtime is connected in the following slice.

## Verification

- Focused Workspace persistence, policy, API and contract tests.
- Existing application route and local-data ownership guards.

## Remaining work

Conversation, Run, Schedule, Tool and frontend integration are not included in
this slice.
