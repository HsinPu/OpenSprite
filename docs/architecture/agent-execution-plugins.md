# Agent execution plugins

## Host API v2

Installed trusted Python packages export no-argument factory providers using `opensprite_backend.agent_loops.v2` and/or `opensprite_backend.execution_policies.v2` entry points.
IDs are stable lowercase identifiers and must not collide. Factories expose integer `api_version = 2`; each `create()` returns a fresh Driver or policy.
Discovery reads metadata without importing code. Only selected compatible entry points are loaded at task acceptance; missing, duplicate, failing or incompatible plugins cannot start a new task.

The text Host exposes `checkpoint()`, `next_turn() -> ModelTurn`, and `finish(turn) -> DriverResult`.
ModelTurn contains text and `final`/`output_limit`; it has no action fields.
Calls are sequential. Turns and results must be the unchanged, same objects issued by the Host.
The core retains credentials, endpoint snapshots, messages, budget calculations, context recovery, output continuation, cancellation, events and persistence.

Policies synchronously return a real bool from `allow_context_retry(ContextRetryState)` and `allow_output_continuation(CompletionState)`.
True allows only core-eligible recovery; False vetoes it. Built-ins are standard and no_recovery, version 2.0.0.
The standard Driver performs checkpoint → next_turn → finish.

## Selection and deployment

`config/execution.json` schema v1 stores Loop/policy IDs. API v2 is the execution interface version, not the settings-file version.
Accepted tasks retain binding objects and package versions; later changes affect new tasks only. `execution.selected` records API 2 and both IDs/versions.
The workbench imports a wheel into `.opensprite/cache/execution-plugin-packages` using bounded static metadata/RECORD validation; it does not run code or install packages.
Deployment bundles build a new image, install the exact wheel, record provenance and use the existing single-writer data volume after a controlled restart.
Installed files are checked against wheel identity; an ID/version match alone is insufficient to confirm deployment.

API v1 is incompatible with the text Host and is never loaded. Old cached packages can be inspected or removed, but cannot be newly imported, selected or deployed.
There is no auto-converter, hot reload, universal extension manager or security sandbox.
See [authoring](execution-plugin-authoring.md) and [clean core](clean-agent-core.md).
