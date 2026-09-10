# Agents async request isolation

## Changes

- Reset cancellation busy state and replace the in-flight set when the parent Run changes. Pending cancellation handlers retain their original set and cannot mutate a new Run's cancellation gate.
- Give Agent editor requests a monotonic identity. Closing or replacing an editor and unmounting invalidate old work; stale success and failure responses cannot overwrite or dismiss a newer draft.
- Preserve the prior workspace scope isolation changes without changing backend contracts or version 0.20.3.

## Verification

- Targeted AgentsSettings and SubagentExecution suites: 21 tests passed, including pending cancellation during a Run switch and both stale editor success/failure after reopening the same Agent.
- Production build and its TypeScript check passed; existing chunk-size warning remains.
- Full frontend suite: 47 files and 406 tests passed. Git diff check passed and SymbolLattice reported a fresh index after the source changes.
- Browser timing simulation and installed runtime verification were not performed. No commit, push, or local installation.
