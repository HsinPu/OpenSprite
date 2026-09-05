# Workspace Run event compatibility

## Objective

Keep execution inspection compatible with valid `run.started` events saved by
OpenSprite 0.11 before Workspace mount metadata was introduced.

## Changes

- Accepted the 0.11 five-field Workspace payload at the frontend SSE boundary.
- Normalized legacy events with the empty mount manifest hash, zero mounts and
  an empty mount list before exposing them to chat inspection state.
- Kept strict rejection for incomplete legacy payloads and malformed current
  mount metadata.
- Added a regression test covering the persisted 0.11 event shape.

## Verification

- The regression test failed before the parser change because the EventSource
  was closed with `malformed_response`.
- Focused frontend tests passed `13` cases and the complete frontend suite
  passed `280` tests after the correction.
- TypeScript typecheck and the production build passed.

## Remaining work

- No commit, push or installed-computer update is included.
