# 0029 - Conversation and Run storage

## Objective

Implement the smallest durable local store required by the approved Agent chat
contract without adding HTTP, model, tool, or frontend behavior.

## Changes

- Added a technology-neutral Conversation repository boundary and immutable
  records for conversations, visible messages, Runs, errors, and semantic events.
- Added a strict schema-version-1 SQLite repository at the explicit AppPaths
  database location with exactly four product tables.
- Made empty reads and repository construction side-effect free; the database
  and `data/` directory are created only by the first successful Run start.
- Added atomic first-message/Run creation, UUID identifiers, exact-request
  idempotency, one-active-Run enforcement, stable pagination, ordered events,
  partial text, completion, safe failure, cancellation, and restart interruption.
- Added a module-boundary test preventing Conversation persistence from importing
  API, runtime, AI settings, Provider connection, or Provider adapter modules.

## Public impact

There is no new HTTP route in this slice. Once later composed, conversation and
Run data will persist under `.opensprite/data/opensprite.db`. No raw credential,
Provider response, internal prompt, hidden reasoning, or absolute profile path
is stored.

## Verification

- Repository tests cover empty reads, first write, idempotency, active-Run
  exclusion, ordered events, partial text, completion, failure, cancellation,
  restart interruption, pagination, corrupt/unknown schema, and concurrent
  starts.
- The complete backend test suite passes with warnings treated as errors.
- Python bytecode compilation and repository whitespace checks run before commit.

## Remaining work

Compose this store through an Agent Run manager, Provider inference adapters,
HTTP/SSE routes, and the real frontend workflow in later slices.
