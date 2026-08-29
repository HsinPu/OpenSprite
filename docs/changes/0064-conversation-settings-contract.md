# 0064 Conversation settings contract

## Objective

Add an independent persisted contract for startup destination and message
sending behavior without changing General Settings.

## Changes

- Added strict `GET` and `PUT /api/settings/conversation` operations with
  `startupView` (`new` or `recent`) and `sendBehavior` (`enter` or
  `modifier-enter`).
- Added lazy defaults and atomic owner-only persistence at
  `.opensprite/config/conversation.json`.
- Added runtime composition, safe error mapping, AppPaths ownership and an
  authoritative OpenAPI document.
- Added the strict frontend API parser and a request-serialized state hook.

## Public impact

General Settings and AI Settings contracts are unchanged. A missing
conversation settings file is side-effect free and returns `new` plus `enter`.

## Verification

- Backend store, malformed data, rollback, same-origin, API and contract tests.
- Frontend provider/consumer payload tests and TypeScript typecheck.
