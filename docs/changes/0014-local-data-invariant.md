# 0014 — Durable local-data invariant

## Objective

Record the approved rule that all future OpenSprite user data belongs below the
single `.opensprite` root.

## Changes

- Added the local-data boundary to the repository instructions so future work
  cannot place conversations, databases, attachments, outputs, memory, state,
  logs, or cache in a second product-data location.
- Strengthened the architecture document with the same durable invariant and
  preserved the native credential-store exception for raw secrets.
- Reaffirmed lazy directory creation and relative database file references.

## Public impact

There is no runtime, HTTP, filesystem-schema, frontend, or installer behavior
change. This slice records a binding rule for future implementations.

## Verification

- Confirmed the repository instruction and architecture sources contain the
  same Windows/Linux root, ownership, credential, and lazy-creation rules.
- Confirmed referenced repository paths exist.
- `git diff --check`: passed.

## Remaining work

Database, conversation, attachment, output, memory, log, cache, and installer
implementations remain deferred until separately approved feature slices.
