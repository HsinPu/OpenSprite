# 0067 Historical Run inspection

## Objective

Let a user inspect the durable execution behind an earlier AI response without
interrupting the current Agent Run or changing backend persistence.

## Changes

- Retained the existing Message `runId` in frontend display state; optimistic
  messages use `null` until the accepted message page is reloaded.
- Added an independent history-inspection hook for Run snapshots and event SSE,
  with stale-response protection, event de-duplication, bounded event state,
  retry, conversation cleanup and terminal stream closure.
- Added a compact inspection action beside assistant timestamps. Terminal Runs
  without an assistant Message receive one fallback action beside their user
  Message; active Runs do not show the fallback.
- Added selected-state semantics, historical loading/error states, the actual
  historical model label and a return-to-latest action in the execution panel.
- Added Traditional Chinese, English and Japanese UI copy.
- Reused the existing Run and event contracts; no backend, database, URL or
  browser-storage change was introduced.

## Verification

- Focused Message identity, inspection lifecycle and ChatWorkspace tests passed.
- Full frontend verification passed: 14 test files and 121 tests, TypeScript
  typecheck and the Vite production build.
- The live desktop browser loaded a historical completed Run with its actual
  model, duration and five replayed events, then returned to the latest Run.
- Collapsed desktop details expanded on selection. Narrow layout scrolled the
  selected details into view with no horizontal overflow or console errors.
