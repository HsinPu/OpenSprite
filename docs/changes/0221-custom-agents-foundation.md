# Custom agents foundation

## Approved objective

Implement version 0.20.0: global and workspace TOML agent definitions, automatic
workspace name shadowing, settings management, and bounded single-level child
executions. Preserve existing 0.19.3 edits. Do not push or update the installation.

## Delivery checkpoints

- [x] Strict definition parsing, paths, catalog, recovery and effective policy.
- [x] Authenticated management API and frontend settings.
- [x] Durable child execution records and bounded coordinator.
- [x] Parent loop discovery, spawn/wait/cancel, Context and tool restrictions.
- [x] Execution inspection UI and three-language copy.
- [x] Full verification, version 0.20.0 and architecture/contracts documentation.

## Constraints

One delegation level; no automatic restart/retry of interrupted children. Children
inherit the parent's workspace and cannot exceed parent tool authority. They may
only use approval-free tools. They do not create sidebar conversations. Parent
termination must settle children. Configuration and definition edits affect new
parent runs only. No new file tools, terminal, or Git functionality.

## Current slice

Add pure AppPaths mappings without creating reserved directories. Definition
parsing is independently implemented and tested before persistence integration.
Add strict catalog IO and a shared pure effective-policy resolver. Workspace
registrations shadow global candidates even when disabled or invalid; current
parsed names participate in collision detection. Execution snapshots are frozen.
This checkpoint is not a completed feature or a release claim.

## Verification

The combined test run passed 42 tests (definition/policy/catalog/AppPaths),
including the missing-persisted-fields regression. Custom-agent compileall passed.
Real Linux GUI/systemd and live model behavior are not yet
verified. Existing SymbolLattice CLI is 0.520.0 (guidance says 0.513.0); host status
reported a fresh index. No index rebuild or tooling update was performed.

## Subsequent checkpoints

Management service, authenticated API and runtime composition have since been
implemented and verified in `0222-custom-agents-management.md`. Child execution,
parent loop and UI integration are recorded in 0223 and 0224. Version metadata is
now 0.20.0; the final release receipt is owned by 0224.
