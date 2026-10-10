# Explicit execution inputs and product composition

- Product version: `0.21.41` -> `0.21.42`.
- Scope: remove product preparation, discovery and eager management imports
  from execution while retaining SDK v5 and the existing product workflows.

The core accepts explicit `RunPreparation` and validated `PreparedRun` inputs.
Workspace checks, model capabilities, response preferences, rendering and
recording policy live in `application/run_preparation.py`. Discovery lives in
`execution_plugins/catalog.py`; background dispatch lives in
`application/run_manager.py`. There is no default Loop selection in the core.
Preparation shares the Run's cancellation and deadline; queued Runs start
after successful preparation, before model inference.

Initializers no longer load product implementations implicitly. All internal
callers now import explicit modules; no retired-path alias was added. HTTP
Provider ID strict validation is preserved in the consumer model. Core DTOs
and canonical identity validation do not require HTTP/Pydantic dependencies.
Request observers receive detached copies. The public v5 author import and
golden contract are unchanged.

Verification includes a new subprocess that rejects product imports and runs
a fresh randomly parameterized custom Loop through the real Host and SQLite.
That fixture tests the protocol; it makes no network calls and claims no model
quality. Separate tests cover preparation cancellation and a shared deadline.
The first native product integration suite passed **78 tests**.
The follow-up isolation, cancellation/deadline, recording fault, SDK, strict
identity and terminal fault suite passed **47 tests**. Verification caught and
fixed queued cancellation during preparation. Core-issued timeout identity is
also retained so timer/clock disagreement cannot turn a deadline into a generic
plugin error. The first Linux broad run passed 1,047 tests and identified one
private cleanup test that needed to invoke the core rather than the new product
composition wrapper; the corrected test passed in the native follow-up.
The final integration stage reruns the complete suite against the final source.
After the timeout ownership fix, **23 cancellation, deadline and terminal-fault
tests passed**. The author download archive was regenerated from all nine
canonical sources; the existing example wheel was not rebuilt.
