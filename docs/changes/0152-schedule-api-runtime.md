# Schedule API and runtime lifecycle

## Objective

Expose the approved durable schedule workflow through authenticated strict HTTP
routes and start the coordinator with the existing backend lifespan.

## Changes

- Added strict schedule CRUD, revision actions, run-now, occurrence history, and
  runtime-continuity routes with stable operation IDs.
- Added unknown-field and duplicate-key rejection plus fixed safe error envelopes.
- Wired one schedule service and one coordinator into the production runtime;
  shutdown stops the coordinator before closing the shared Agent run owner.
- Added read-only host continuity detection. Windows reports login-only behavior;
  Linux reports linger state when `loginctl` can confirm it.
- Added the authoritative schedule OpenAPI contract.

## Security and compatibility

All schedule routes remain behind the existing default-deny local authentication
middleware. Host continuity detection never changes system configuration, invokes
a shell, or requests elevation.

## Verification

- HTTP tests cover CRUD, pause/resume, run-now, history, stale revisions,
  unknown fields, duplicate JSON keys, and authentication protection.
- Runtime and application route-contract regressions remain green.
- Python source and tests compile successfully.

## Remaining work

The frontend schedule page, Linux installer warning, version/docs update, and
full repository verification remain separate slices.
