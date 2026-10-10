# Agent Loop plugins — Host API v5

OpenSprite 0.21.35 separates general execution mechanisms from text policy.
A trusted Python wheel exports a no-argument factory provider under
opensprite_backend.agent_loops.v5. Its factory has integer api_version = 5;
synchronous create() returns a fresh instance with async execute(host).

| Loop decides | Host provides/enforces |
| --- | --- |
| History selection, ordering, wrappers, message roles, prompts | Raw paginated data, immutable admission boundary, source ownership |
| Soft input/output allocation, recent floor, summary triggers | Pinned model/user hard limits and conservative input validation |
| Summary input, prompt, generation, output transformation and format | Generic draft inference, contiguous source hash, CAS and atomic summary/event storage |
| Retry/backoff, continuation prompt, tail and stopping behavior | Single model request per infer, safe errors, request lineage and shared Run ceilings |
| Draft/review/revision and selected final answer | Private step history, append-only answer stream, one terminal transaction |

RunExecutor owns lifetime and terminal persistence. LoopExecutionHost does not
assemble context, prepare summary prompts, retry or continue. The independent
opensprite-standard-loop==0.2.0 wheel owns the standard recent-12, 75%/55%
selection, automatic context sizing, summary instructions, one
eligible context recovery, continuation tail and stopping policy. No executable
fallback lives in the core. no_recovery uses the same preparation but omits
context retry and output continuation.

## Product composition and isolated execution

`application/run_preparation.py` owns product preparation: workspace checks,
model-capability resolution, response preferences, product Prompt construction
and the opt-in request recorder. `ProductRunExecutor` delegates those inputs
to the core; its standard Loop default is a product choice. Metadata discovery
and installed-plugin management live in `execution_plugins/catalog.py`.
Background task dispatch and Provider usage references live in
`application/run_manager.py`.

The core `agent/run_executor.py` requires an explicit `RunPreparation`. A
`PreparedRun` contains a fixed base Prompt, limits, selected factory, non-secret
endpoint and start metadata. The same RunControl covers preparation and Loop
execution; preparing a Run does not restart its deadline. A Run stays queued
until preparation succeeds, then starts before model inference. The core never
discovers plugins, reads product preferences or selects a default Loop.

Package initializers do not eagerly import App or management implementations.
The core imports technology-neutral records and protocols; pure workspace and
endpoint records remain shared data, without filesystem or network services.
Provider ID HTTP validation stays in consumer models while its core type and
canonical identity validator require no Pydantic. Optional request observers
receive detached request copies and cannot mutate the transmitted inputs.

## Public SDK

All public types are available from opensprite_backend.agent.plugin.

- run: fixed identity, Provider/model IDs, system prompt,
  user context/output choices, ModelLimits and ExecutionLimits. Automatic soft
  allocation belongs to the Loop. Explicit user choices cap the model limits.
- checkpoint(): cooperative cancellation/deadline check.
- read_context(ContextReadRequest): zero inference calls. Returns raw Messages,
  separately identified current_user, a format-scoped summary and cursors.
  limit is 1..200. Default/before_sequence reads a newest page in ascending
  sequence order; after_sequence reads the oldest next page. Do not mix cursors.
  All history excludes the admitted user message and anything after it.
  summary_format=None disables summary reading.
- estimate_input(tuple[ModelMessage]): generic conservative estimation. It
  chooses no history or output budget.
- infer(StepRequest): exactly one provider call, or a context-limit StepResult
  before contacting the provider if the prepared input is too large. messages is
  the complete tuple, including system message. The first system content must
  start with the pinned workspace system prompt. Host does not insert wrappers.
  max_output_tokens is mandatory. Optional input_limit_tokens is a tighter
  Loop-selected input budget, within context minus output reserve.
- save_summary(SummaryWriteRequest): zero provider calls. Saves the Loop-selected
  text from an owned summary-generation step. Repeating the same write returns
  the original summary without a second completion event.
- finish(FinalOutput): validate the chosen final text/error, then return the
  exact issued RunResult. The executor commits the terminal state after execute
  returns. No operation is allowed afterward.

InputSource binds a message position to owned snapshot message IDs, summary ID
or prior StepResults. Main/continuation inputs must declare the admitted user's
source. Loops can transform, combine and reorder data; source checks establish
provenance, not semantic equivalence or factual accuracy. Actual input hash and
token receipt describe the transmitted messages. Receipt schema 3 adds stepIds;
schema 2 remains readable for historical diagnostics. Neither contains raw
prompt text. Full prompt logging remains an explicit sensitive-data preference.

## Summary consistency

A summary-generation infer uses purpose="compaction", channel="draft",
SummarySource and matching InputSource IDs. The Loop supplies complete prompt
messages, output budget, source pages, previous summary ID and format.
Sources must belong to this Host and form an ordered, contiguous older prefix:
first sequence 1 without a prior summary, otherwise prior coverage plus 1.
The current user cannot be summarized. The Host independently hashes canonical
previous-summary coverage/hash/content plus raw source role/sequence/content.

The generated StepResult does not automatically become a summary. The Loop can
reject it, transform it or save it explicitly. Persistence compares the declared
previous summary with current stored coverage in the same transaction that
inserts the summary and context.compaction.completed. Failed writes leave both
absent. source_step_id, source_first_sequence and previous_summary_id record the
provenance chain. Validation does not certify the meaning of generated text.

## Errors, output and limits

All operations are awaited sequentially. Forged, copied, mutated or cross-Run
snapshots/steps/results fail closed. Swallowed fatal errors, overlapping calls
and calls after finish cannot produce a successful Run. Recoverable inference
errors are returned in StepResult; retry_of must identify the owned failed
retryable step. A partially published answer cannot replay that step.

Draft output stays in authenticated step history. Answer output streams and is
append-only; final text must retain its published prefix. Finish can publish
selected/transformed draft text while keeping unused drafts private.

Standard Loop automatically continues OUTPUT_LIMIT, stopping on FINAL, repeated
OUTPUT_LIMIT segments, unrecoverable context limits, cancellation or shared Run
ceilings. There is no global continuation count or separate 64-request ceiling.
A custom Loop owns its own stopping policy. Defaults remain 128 total actual
model requests, 32 summary-generation calls, 600 seconds, 1,048,576 generated
characters and 2,048 Host operations. Summaries, retries and continuations all
consume the same counters. Python plugins are trusted in-process code:
checkpoint/deadline handling is cooperative, not process isolation or a sandbox.

## Admission and migration

Metadata-only discovery does not import plugin Python. Admission pins factory
and distribution version and transactionally saves the profile with the user
message/Run. Replay looks up the accepted Run before mutable settings.

New wheel import/deployment accepts API v5 only. API v1..v4 wheels remain
inspectable but incompatible; rewrite SDK use, entry point and factory, then
build a new wheel. No compatibility executor is added.

AI settings schema 12 atomically migrates schemas 3..11 and removes the obsolete
outputContinuation setting. SQLite schema 23 transactionally upgrades 20/21/22,
preserving all original columns, rows, text, IDs, legacy continuation choices and
opaque archived tables. New runs store NULL in the historical continuation
column. Summary provenance columns are nullable for legacy summaries. An
unexpected schema rolls back without advancing the version. Older backends
must not write the upgraded database. Restart interrupts unfinished Runs/steps.

Settings revision conflicts, package review/import and deployment confirmation
keep their existing behavior. Import stores reviewed bytes; it neither installs
nor selects a Loop. Docker bundles install a wheel into a rebuilt API v5 image
as UID 10001; both desktop installers bundle the official wheel as an ordinary
distribution. Keep one writer and back up the entire sensitive .opensprite
directory before upgrading actual user data.

See execution-plugin-authoring.md for complete source, tests and installation.

## Core stop evidence (0.21.36)

Limits are enforcement mechanisms. A terminal `run.failed` can include a
`limit` object (`kind`, `maximum`, `used`), committed with the failed Run.
Kinds are `duration_seconds`, `model_requests`, `summary_requests`,
`generated_chars`, and `host_operations`; each has its own public error code.
Duration is elapsed seconds from the original Run deadline. Other kinds are
accepted counts and exclude the rejected operation or complete text delta.
Retries, summaries and continuations consume the same Run budget. The
workbench diagnostics display and export this evidence. Legacy
`agent_limit_reached` events remain readable without invented measurements.
`PublicRunError`, factory entry points and Host API v5 shapes stay unchanged.

## Run enforcement composition (0.21.37)

`RunManager` owns live tasks, cancellation and shutdown. `RunExecutor` owns
setup and the terminal transaction. `LoopExecutionHost` receives its
repository, traced gateway, prompt writer and one `RunControl` explicitly;
it never reads executor private fields. RunControl starts before factory
creation and shares one absolute deadline, cancellation signal and accepted
request/summary/text/operation counters across setup and every Host call.
Only an expired core deadline produces deadline evidence; a raw TimeoutError
from a plugin or setup dependency is an internal error. RunControl cancels
and drains its pending await/stream tasks, without scheduling recovery or
renewing any budget. Trusted Python still requires cooperative awaits.

## Stable v5 SDK data (0.21.38)

The only supported author import remains `opensprite_backend.agent.plugin`.
The pinned `contracts/agent-loop-v5.sdk.json` records the v5 field order,
logical types, defaults, enum values, factory and Host signatures captured
before this refactor. Patch releases must pass this contract and an
unchanged prebuilt wheel; incompatible changes require a separately approved
new API. SDK data is independent of conversation storage and inference DTOs.
The Host explicitly copies stored messages, summaries and errors into public
frozen records and converts full model inputs to transport records once,
preserving receipt object bindings. Executor converts public errors and
completion reasons before storage. Authors must import public enum/record
types from the SDK, without assuming internal transport/storage class identity.
Entry points, factories and the official/example wheel versions are unchanged.

## Atomic terminal decisions and crash recovery (0.21.39)

Cancellation committed before a failure transaction wins within that same
SQLite transaction: the Run becomes cancelled, with one cancellation event
and no failure or limit evidence. Cleanup preserves an already committed
terminal state, including completion committed before a notification fails.
Status, messages, summaries and their events must commit together or roll back
together. Restart marks unfinished Runs interrupted without resending model
requests; only previously committed text is retained. Repository verification
scripts exercise real SIGKILL during public/private streams and summary/final
transactions. This proves process-crash recovery, not unflushed text retention
or power-loss durability. Trusted in-process Loops still require cooperative
awaits and are not a security sandbox.
