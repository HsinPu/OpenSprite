# 0056 Frontend chat reliability

## Objective

Close the reviewed responsive-navigation, pagination, asynchronous race, and
retry gaps without changing the Agent Chat or General Settings HTTP contracts.

## Changes

- Made the narrow-screen navigation sidebar and background workspace mutually
  exclusive for keyboard and assistive-technology interaction.
- Added explicit cursor-based loading for older Conversations and Messages.
- Added request generations so stale refresh, pagination, stream, and cancel
  results cannot overwrite the newly selected Conversation.
- Preserved a durable partial assistant response until replay supplies fresh
  deltas or terminal Messages become authoritative.
- Added a retry action for failed General Settings startup reads.
- Removed asynchronous React test warnings and added regressions for each
  corrected workflow.

## Public impact

HTTP payloads, Provider behavior, Agent Run semantics, persisted schemas, and
URL hashes are unchanged. The browser now exposes localized load-more controls
only when the corresponding backend cursor exists.

## Verification

- Complete frontend Vitest suite: 12 files and 99 tests passed without React
  test warnings.
- TypeScript no-emit typecheck passed.
- Vite production build passed.
- Narrow-screen browser verification confirmed sidebar/background interaction
  isolation.

## Remaining work

- The production bundle still reports Vite's non-blocking large-chunk warning.
  Route-level or feature-level code splitting is a separate performance slice.
