# Workspace management interface

## Objective

Expose Workspace selection and management in the existing desktop and mobile
conversation experience.

## Changes

- Added a Sidebar Workspace switcher backed only by the server-side active
  Workspace value.
- Added a Settings Workspace page with responsive create/edit dialogs, native
  directory selection, availability, usage and safe removal states.
- Scoped conversation navigation to the active Workspace, resolved deep links,
  and added guarded Conversation move controls.
- Added Workspace selection to Schedule editing and an unavailable-root warning
  that leaves text chat enabled.
- Added strict frontend Workspace adapters, React state ownership and complete
  Traditional Chinese, English and Japanese copy.
- Exposed schedule-managed Conversation ownership so the UI cannot offer an
  invalid move action.
- Reflowed the mobile composer controls into two rows so the Workspace release
  preserves a 390 px viewport without horizontal overflow.

## Public impact

Users can create, select, edit and remove empty Workspaces, move normal
Conversations, and assign Schedules to an explicit Workspace.

## Verification

- Workspace API, hook, Settings, Sidebar, deep-link and move tests.
- Schedule selector, unavailable-root and three-locale tests.
- Backend Conversation ownership and contract tests.
- Frontend TypeScript and production build checks.
- Desktop browser creation/switching checks and a measured 390 x 844 Chrome
  viewport with document width equal to viewport width.

## Remaining work

File tools, Git, terminals, Skills and external channel adapters remain outside
this release.
