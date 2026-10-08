# Agent Loop plugins — API v3

An installed trusted Python wheel exports a no-argument factory provider through **only** `opensprite_backend.agent_loops.v3`. A factory advertises integer `api_version = 3` and its synchronous `create()` returns a fresh complete plugin for every Run.

The same instance implements `async execute(host)`, `allow_context_retry(state)` and `allow_output_continuation(state)`. There is one executable plugin category, one selection, one package version and one Run-local instance. Recovery callbacks return an actual bool synchronously; they must be fast and perform no I/O.

Discovery and settings GET/PUT read metadata without importing Python. Admission resolves and pins the selected factory and package version. A load failure rejects admission without a user message or Run; instance creation or execution failure terminally fails the accepted Run with a sanitized error. No fallback silently changes the selected plugin.

## Core authority

`opensprite_backend.agent.plugin` defines the public contract and immutable `ModelTurn`, `DriverResult`, `ContextRetryState` and `CompletionState`. The Host exposes `checkpoint()`, `next_turn()` and `finish(turn)`. API v3 permits one main `next_turn`; eligible recovery and output continuation stay inside the Host. This version does not add multi-turn planning.

Host calls must be awaited sequentially. The unchanged Host-issued turn goes to finish; the unchanged Host-issued result is returned. No model operation follows finish. Core gates, budgets and configured bounds precede recovery callbacks; True cannot grant extra retries, continuation, prompt changes or credentials. The core retains Provider endpoints, transcripts, cancellation, SSE, context compaction and all persistence. A plugin can veto eligible recovery.

The `standard` built-in allows core-eligible recovery and configured continuation. `no_recovery` uses the same text flow and vetoes both. Both are version 3.0.0. Plugins are trusted in-process Python, not a sandbox. Cancellation of Python code is cooperative; the core cannot forcibly terminate arbitrary uncooperative code.

## Admission and immutable history

New production Runs store `execution.selected` in the same SQLite transaction as acceptance:

```json
{"pluginId":"standard","pluginVersion":"3.0.0","apiVersion":3}
```

An idempotent replay is checked before mutable settings or loading factories; it neither rebinds the plugin nor makes another model request. Changes affect new Runs only. Existing API v2 profile events retain their raw bytes and remain readable as historical Loop/policy metadata; no API v2 code is loaded.

`config/execution.json` schema 2 stores `version`, positive `revision` and `pluginId`. Absent settings implicitly select standard at revision 0 without creating data. PUT requires `expectedRevision` and increments it under the sole settings writer's lock; stale writes return 409 without overwriting. Known schema-1 pairs standard/standard and standard/no_recovery migrate atomically once. Any external pair stays unchanged, reports explicit migration information, and blocks new Runs until an API v3 choice is applied. Back up the complete sensitive `.opensprite` before upgrading.

## Wheel and Docker

Static bounded ZIP/metadata/dependency/RECORD validation never imports code. New imports accept only agent_loops.v3. Cache schema 2 is written for new packages; schema 1 remains readable for inert history. API v1/v2 cached wheels report `needs_update` and cannot be redeployed. Retired policy groups are recognized only during old-cache inspection.

Deployment bundles install the exact wheel offline into a derived image, check installed files and entry points, and write schema-2 provenance. Runtime verification reads old provenance too without executing plugin code. A same ID/version does not prove an exact deployment. Use an API v3 base image and rebuild all retired external plugins; a bundle fails if retaining an incompatible deployed package. Keep the existing Compose project and single-writer data volume and end active Runs before restart. Import does not install or select; return to verify deployment and explicitly apply the discovered Loop.

See [authoring](execution-plugin-authoring.md) and [clean core](clean-agent-core.md).
