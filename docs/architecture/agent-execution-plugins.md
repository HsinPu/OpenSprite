# Agent Loop plugins — API v4

OpenSprite 0.21.34 separates execution decisions from bounded effects. A trusted
Python wheel exports a no-argument factory provider in
`opensprite_backend.agent_loops.v4`. Its factory has integer `api_version = 4`
and synchronous `create()` returns a fresh instance implementing only
`async execute(host)`. There is one executable plugin category and one choice.

## Responsibility boundary

| Loop decides | Core Host enforces |
| --- | --- |
| Number/order of inference steps and stage instructions | One model operation per infer; pinned Provider/model/reasoning settings |
| History selection, recent-message floor and selection target | Immutable admission history; current user always included; actual input budget |
| Summary trigger, contiguous source range, format and instructions | Source ownership/hash/coverage; one compact call; durable provenance |
| Recoverable retries, backoff and continuation prompts | Error classification, user continuation ceiling, cancellation and resource ceilings |
| Draft/review/revision and final text | Private draft storage; append-only answer stream; exactly one terminal transaction |

`RunExecutor` owns Run lifetime and terminal persistence, without iteration or
strategy. `LoopExecutionHost` exposes checkpoint/context/infer/compact/finish.
It never automatically summarizes, retries or continues. The independent
`opensprite-standard-loop==0.1.0` wheel owns the standard recent-12, 75%/55%
selection, summary instructions, one eligible context retry, continuation tail
and stopping choices. `no_recovery` uses the same preparation but omits retries
and continuation. Both are discovered through installed metadata. Missing the
official package fails admission; there is no built-in executable fallback.

The official wheel is bundled with the backend via a relative uv source to
avoid a runtime dependency cycle. It requires the product's API v4 SDK and is
not a standalone application. Docker and both desktop installers include and
install this source as an ordinary distribution.

## Public operation semantics

The immutable dataclasses live in `opensprite_backend.agent.plugin`.

- `host.run`: read-only Run IDs, model, budget, continuation choice, limits and selected plugin version.
- `context(ContextSpec)`: assemble a bounded context without model calls.
  `recent_messages` is 1..64, `selection_tokens` is at most the input budget,
  `history_ids` selects from the latest 200 raw messages (current user is always
  retained), and `summary_format` scopes compatible coverage.
- `infer(StepRequest)`: one streamed model request; added messages are only
  user/assistant text. `instruction` supplements the fixed system prompt.
  `channel="draft"` persists text privately; `answer` also streams it publicly.
  Returns a StepResult with text, finish reason, usage and optional safe error.
- `compact(CompactionSpec)`: one draft inference of an owned, contiguous older
  prefix; the Loop supplies format and instructions. Returns step plus persisted
  summary, or step plus None when recovery is needed. A stale context cannot
  replace newer coverage. Source hash and producing plugin ID/version are saved.
- `finish(FinalOutput)`: validate final output or an owned step/context failure.
  Return the exact issued RunResult. RunExecutor performs the terminal transaction
  after the plugin returns; finishing is not a second Run completion.

Await operations sequentially. Parallel/replayed/mutated contexts, steps or
results, operations after finish, fabricated public exceptions and swallowed
fatal Host failures cannot become successful Runs. Draft text may be revised;
published answer text must remain a prefix of final text. This permits a draft
step to be selected/transformed and published at finish without publishing other drafts.

Recoverable context/rate-limit/timeout/unreachable errors are StepResult errors.
Retries explicitly reference the owned failed step via `retry_of`; a partially
published answer cannot be retried. Authentication, malformed provider output,
storage failures, cancellation and hard ceilings stop execution. The standard
Loop handles only its documented context recovery; other retries are author policy.

Default ceilings: 128 total actual model requests (including summaries/retries),
32 compactions, 600 seconds of cooperative execution, 1,048,576 generated text
characters, 2,048 Host operations. Smaller bounds are useful in regression tests.
User continuation settings impose a further ceiling of 64 for unlimited.
No hidden extra continuation requests are made after a final answer.

## Admission, data and diagnostics

Discovery and settings read metadata without importing Python. Admission pins
the factory and distribution version and persists the profile in the same
transaction as user message/Run creation:

```json
{"pluginId":"standard","pluginVersion":"0.1.0","apiVersion":4}
```

Idempotent replay reads the accepted Run before mutable settings. Settings
schema 2, expectedRevision/409 behavior and explicit external-choice migration
are unchanged. API v2/v3 events remain readable without rewriting or executing
the old package. New import/deployment accepts API v4 only.

SQLite schema 22 adds run_steps and format-scoped summary provenance. Upgrades
from 20/21 transactionally copy all existing event and compaction columns/rows
before replacing their constraints; no old text/IDs are discarded. Unexpected
schemas fail without advancing the version. Older schemas need the preceding
upgrade path. Restart marks active Runs and unfinished steps interrupted.
An upgraded database cannot be written by the older backend.

step.started/step.completed carry bounded stage labels/status/usage, never draft
text. GET /api/runs/{run_id}/steps is a same-origin, authenticated when configured,
100-row paginated endpoint for persisted draft/answer text and retry references.
Only answer deltas/final text become conversation messages. Draft is visible
model output, not hidden reasoning; provider reasoning remains filtered.
The workbench shows generic stages and step detail, without branching on plugin IDs.
model.attempt preserves actual request/attempt lineage and content-free receipts.

## Wheel trust and delivery

Import validates bounded ZIP, metadata, dependencies and RECORD without execution.
Imported bytes are a cache, not installation or selection. Deployment installs the
exact wheel offline, verifies installed files/entry points and saves provenance.
Retired wheels stay readable as needs_update; they cannot be deployed on API v4.
Use an API v4 base image and rebuild any retained incompatible external packages.

Python plugins run with backend privileges in process. Static wheel validation
and frozen dataclasses do not create a sandbox. Cancellation/time limits apply to
cooperative async code; uncooperative blocking Python requires future process
isolation, which is outside this change. No tools, Skill, Subagent, MCP, scheduler,
command shim or generic lifecycle mechanism is introduced.

See [authoring](execution-plugin-authoring.md) and [clean core](clean-agent-core.md).
