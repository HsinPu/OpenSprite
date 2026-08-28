# 0055 Backend reliability hardening

## Objective

Close the reviewed Agent terminal-state and Provider persistence reliability
gaps without changing the HTTP or frontend contracts.

## Changes

- Added a shared 1,048,576-character assistant-output limit checked by the
  Agent before SQLite persistence.
- Made the Run manager convert recoverable background persistence failures into
  a safe terminal Run failure instead of silently discarding the task.
- Added a strict non-secret Provider mutation journal below `.opensprite/state`
  so startup can finish or roll back a credential/metadata mutation interrupted
  between its two atomic file replacements.
- Hardened Provider metadata with a 1 MiB read/write cap, duplicate-key
  rejection, one repository lock, owner-only POSIX permissions, and directory
  fsync after replacement.

## Public impact

HTTP payloads, error envelopes, Provider IDs, credential encryption, model
selection, and frontend behavior are unchanged. A transient
`state/provider-transaction.json` file may exist only while a Provider connect
or disconnect mutation is incomplete; it contains no API key or ciphertext.

## Verification

- Focused Agent, Run manager, Provider state, Provider transaction, AppPaths,
  Provider runtime, and runtime-lifecycle tests.
- Complete backend pytest suite with warnings treated as errors.
- Python compileall, offline lock check, dependency compatibility check, and
  repository diff checks.

## Remaining work

- The large SQLite repository remains one concrete adapter. Splitting it is a
  later behavior-preserving refactor and was intentionally excluded from this
  reliability fix.
