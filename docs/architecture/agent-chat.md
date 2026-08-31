# Agent chat architecture

## Purpose

OpenSprite treats each submitted user message as one bounded agent run. Every
message enters the same path; there is no keyword classifier, legacy Task
lifecycle, or alternate direct-to-model branch.

```text
Browser UI
  -> Conversation and Run HTTP API
  -> Application orchestration
  -> Run manager
  -> Agent loop
     -> Model gateway -> one Provider adapter
     -> Tool registry -> policy -> explicitly registered tool
  -> SQLite conversation store
  -> semantic Run events -> SSE -> Browser UI
```

## Domain ownership

- A **Conversation** is a durable user-visible thread.
- A **Message** is durable visible user or assistant content. Internal prompts,
  raw Provider payloads, tool arguments, secrets, and hidden reasoning are not
  messages.
- A **Run** is the execution caused by one user message. It snapshots Provider,
  model, response mode, Context budget, status, completion reason, safe error,
  partial assistant text, and timing. Context budget remains internal and does
  not expand the public Run payload.
- A **Run event** is a small durable semantic projection used for replay and UI
  status. Events never contain credentials, raw upstream bodies, or hidden
  chain-of-thought.
- A **Tool call** is an in-memory step inside a run. Only its safe name, status,
  and bounded public summary may become a Run event.

The dependency direction is fixed:

```text
API -> Application -> Agent -> Inference
                     |  -> Tools
                     `-> Conversations
```

`Application` owns the use-case coordination between AI settings, Provider
connection state, durable Conversations and the Run manager. It does not import
FastAPI, HTTP serializers or concrete persistence adapters. `Conversations`
must not import Provider adapters. `Tools` must not import the Agent loop.
Provider adapters perform no persistence. The API validates and serializes the
contract but does not implement model, tool or persistence behavior.

## Public workflow

1. `POST /api/runs` receives a nullable conversation id, a client-generated
   request id, and one non-empty user message.
2. Backend settings select one connected Provider and model. The message,
   conversation, and queued Run are committed in one SQLite transaction.
3. The Run manager starts the bounded Agent loop after the durable start
   transaction succeeds.
4. The loop resolves the selected model capability, converts the Run's Context
   policy into an input budget, retains the recent message floor, and compacts
   only older history when required.
5. The browser opens `GET /api/runs/{run_id}/events`. Persisted events replay in
   sequence and then stream over SSE; reconnect uses `Last-Event-ID`.
6. Text deltas update the Run partial text and UI. A natural stop completes the
   Run. An output limit may enter the Run-snapshotted continuation policy;
   every attempt appends to the same Run and eventual assistant Message.
7. A structured model tool request must match an explicitly registered tool and
   pass policy before execution. Tool output returns to the same Agent loop.
8. Cancellation, limits, Provider failure, or shutdown move the Run to an
   explicit terminal state. They do not fabricate an assistant success message.

The request id is the idempotency boundary for retries. A conversation may have
only one queued, running, or cancelling Run. A new conversation is created only
when the first user message is durably accepted.

This workflow is now composed in the local system runtime. `AgentChatService`
reads the atomic AI setting, verifies the selected Provider still has encrypted
credential metadata, commits the user Message and Run, and only then asks
`RunManager` to schedule execution. The API layer validates and serializes the
contract but does not call a Provider, execute a tool, or write SQLite directly.

At Run start, the injected System Prompt provider renders one trusted snapshot
from the confirmed locale, time-zone setting and current time. The exact same
snapshot is used for every model round in that Run. Before the first Provider
request, a complete create-only Prompt receipt must be fsynced below
`.opensprite/logs/system-prompts`; logging failure prevents the Provider call.

| Route | Responsibility |
| --- | --- |
| `GET /api/conversations` | Reverse-updated cursor page for the sidebar. |
| `GET /api/conversations/{id}/messages` | Visible Message page in ascending sequence. |
| `POST /api/runs` | Idempotently accept one user message and queued Run. |
| `GET /api/runs/{id}` | Read the durable snapshot, partial text, completion reason, status, and safe error. |
| `GET /api/runs/{id}/events` | Replay and follow events after `Last-Event-ID`. |
| `POST /api/runs/{id}/cancel` | Bodyless cancellation of queued or running work. |

SSE frame ids are durable positive event sequences and frame event names equal
the semantic event type. Opening after completion replays the missing suffix and
closes. The browser closes its EventSource after receiving a terminal event.

## Browser workflow

The sidebar reads `GET /api/conversations` and identifies a selected
conversation only by its backend UUID in the URL hash. A new conversation has
no durable identity until `POST /api/runs` accepts its first message; the
returned conversation UUID then replaces the temporary new-chat state.

The browser keeps the submitted user message visible while acceptance is in
flight, follows named semantic events over SSE, and appends only
`assistant.delta` text to the live assistant surface. At a terminal event it
reloads both the durable Run snapshot and visible Messages rather than treating
the stream buffer as authoritative. Duplicate replayed event sequences and
events belonging to an obsolete selected conversation are ignored. An active
Run exposes a stop action through the bodyless cancellation operation.

Persisted Messages retain their authoritative `runId` in frontend display
state. An assistant Message exposes one history-inspection action beside its
timestamp; a terminal Run without an assistant Message exposes the fallback
action beside its user Message. Inspection reads the existing Run snapshot and
replays its events through a separate EventSource, so selection, retry and
cleanup cannot close or replace the live Run stream. The execution panel uses
the inspected Run's provider/model identity and can return to the latest Run.
No additional API, database table, browser storage or persisted cache is used.

Conversation and Message cursors are explicit browser state. The sidebar can
append older Conversation pages without replacing the current page, while an
open Conversation can prepend older Message pages without changing ascending
message order. Refresh, pagination, cancellation, and stream callbacks carry a
selection generation; a result from an older generation cannot overwrite or
surface an error in the newly selected Conversation. A stored partial assistant
response remains visible until replayed deltas replace it or durable terminal
Messages become authoritative.

The conversation viewport owns auto-follow independently from Run and SSE
state. Opening a Conversation positions its latest Message once. With
`autoScroll` enabled, an explicit local send follows the new optimistic Message;
streaming output continues to follow only while the viewport remains within 96
pixels of the bottom. Manual upward scrolling pauses follow and returning near
the bottom resumes it. Disabling the preference prevents send and streaming
updates from changing scroll position. Prepending older Messages always
compensates for the inserted height so the visible anchor does not move. These
updates are coalesced through one animation frame and do not alter the mobile
history-inspection navigation behavior.

On narrow screens the sidebar behaves as a modal navigation surface. While it
is closed it is removed from keyboard and accessibility-tree interaction; while
it is open, the conversation workspace is inert until navigation is dismissed.
Desktop sidebars keep their independent collapse behavior.

The execution panel is a projection of the selected Run and its semantic
events. It displays the fixed Provider/model/mode snapshot, safe status and
timing, and only tool names that actually appeared in persisted tool events.
Its outer disclosure is collapsed by default. The confirmed Conversation
Settings preference may default it open; manual disclosure changes remain local
to the mounted Conversation and never write settings. Historical Run inspection
expands the panel when entered, and returning to the latest Run restores the
confirmed default. Run and event updates do not reset a manual disclosure
choice, including after entering historical inspection.
Closing the desktop header disclosure while historical inspection is active also
returns to the latest Run, so the hidden panel cannot leave a historical message
marked as selected.
Because the current production Tool Registry is empty, the UI explicitly says
that no extra tool was used and does not advertise Search, File, Memory, or any
other speculative capability.

## Persistence

The first implementation uses only four SQLite tables under
`.opensprite/data/opensprite.db`:

- `conversations`
- `messages`
- `runs`
- `run_events`

Identifiers are backend-generated UUIDs, except `clientRequestId`, which is a
browser-generated UUID used only for idempotency. Database records never store
an absolute user-profile path. Future large output files must use AppPaths and
persist only paths relative to `.opensprite`.

Queued or running work cannot be resumed safely after a process restart. Startup
therefore marks non-terminal Runs as `interrupted`; it does not silently retry a
Provider request or tool side effect.

## Agent bounds and tool policy

The initial loop is intentionally small:

- at most 8 model rounds;
- at most 16 tool calls;
- at most 1,048,576 characters of accumulated assistant output;
- duplicate failed calls stop instead of retrying forever;
- each tool has an explicit timeout and output cap;
- cancellation is checked before model and tool boundaries.

Context is bounded by tokens rather than a fixed number of Messages. `auto`,
32K, 64K, 128K, 256K and model-maximum choices resolve against a backend-trusted
model capability. Output choices are Auto, 8K, 16K, 32K, 64K, and model
maximum. Auto targets one quarter of the selected Context with a 32K ceiling;
all modes remain capped by model capability and reserve at least 25% of Context
for input plus a 10% safety margin of at least 4K. Compaction begins at 75% of the remaining input
budget and targets 55%. The current user message and recent 12 visible Messages
are mandatory; if they cannot fit, the Run fails with `context_limit_exceeded`
instead of silently dropping them.

The composer displays the latest provider-facing Context estimate beside the
model picker as `used / effective limit`. The estimate includes the rendered
System Prompt, summary, selected history, current user Message and tool
definitions, and is calculated by the backend's conservative counter. It is a
diagnostic indicator rather than billing usage; a missing value is shown as `—`.
The warning color compares the estimate with the safe input budget, while
compaction and Context-limit decisions remain backend-owned.

Older history is summarized through the selected model with tools disabled and
a 2K output limit. Append-only compaction records keep monotonic sequence
coverage, a source hash, model provenance and usage counts. Raw Messages are
never deleted or replaced and can rebuild every summary. The summary enters the
model transcript as explicitly marked historical user data, never as a trusted
System instruction. History Messages are likewise wrapped as quoted historical
data; only the active Run's current user Message remains an actionable user
instruction. This boundary is applied again after compaction and before
continuation requests, while the original database Messages remain unchanged.
Each tool round is recounted before its Provider request.
Safe structured logs contain only limits, estimated or reported token counts,
message counts and compaction coverage; they never contain prompt or Message
content.

When `logFullPrompts` is explicitly enabled in AI Settings, the Agent writes a
separate immutable request receipt before each main or continuation model call
under `logs/prompts/<local-date>/<run-id>/`. It contains the exact provider-neutral
messages sent at that boundary, including the rendered System Prompt, user
message, included history/summary, continuation tail and tool results. This
deliberate diagnostic log is separate from `backend.log`, is size-bounded and
owner-protected; it is disabled by default and never includes credentials or
the model response.

When OpenRouter omits `max_completion_tokens` for router-style model aliases,
the capability boundary uses a Context-bounded 32K fallback on both backend and
frontend. Explicit model capability always wins. Provider truncation still
flows through the durable `output_limit` completion path.

Each Run snapshots the requested output budget and output-continuation policy.
Response delivery is a browser presentation preference: the backend and all
Provider adapters continue to stream semantic events, while the browser may
buffer assistant deltas until the Run reaches a terminal state.
SQLite schema v8 converts the former boolean to `2` or `off` while preserving
Messages, Runs and events. The
resolved token number is persisted on every `model.started` event and shown in
the execution record, so later settings changes cannot rewrite historical
execution behavior. Existing Runs migrate to `auto`; pre-v5 model events record
the former product limit of 8,192 tokens. New `model.started` events also carry
the conservative input estimate, effective Context limit and safe input budget;
these fields are optional so older persisted events remain replayable.

Immediately before a real compaction model request, the Agent appends the
empty-payload semantic event `context.compaction.started`. The browser uses it
only as transient progress and as a safe execution-record step. It never becomes
a Conversation Message, never contains the generated summary, and is cleared by
the next model or terminal Run event.

The Agent checks the shared assistant-output limit before every durable delta,
so a Provider cannot push the SQLite Run beyond its storage contract. If an
otherwise recoverable repository write fails during background execution, the
Run manager makes one fail-closed terminal transition with a safe internal
error; it does not silently discard the task while leaving an active Run.

Automatic continuation is owned by the backend Agent loop, not by the browser.
Each Run snapshots `off`, 1, 2, 3, 5, or `unlimited`; the default is 2. The
unlimited policy still stops at 64 continuation requests, the assistant size
bound, cancellation, Context exhaustion, invalid output, or Provider failure.
Continuation disables tools and adds no synthetic user Message. Each attempt
records `response.continuation.started`; `maxAttempts` is null for unlimited.
The continuation request retains the original transcript plus at most 4K
estimated tokens from the current assistant tail. If that cannot fit, the loop
may compact older conversation history once before the attempt. A remaining
Context limit with existing text completes one durable partial response with
reason `context_limit`; no-text Context failures remain failed Runs.

Provider output limits are normalized separately from malformed responses.
OpenRouter `length`, OpenAI incomplete max-token responses, and Anthropic
`max_tokens` or `model_context_window_exceeded` become `output_limit`. When
bounded text exists and no tool call is incomplete, that text is committed as
a visible assistant Message with completion reason `output_limit` when
continuation is disabled or exhausted. Missing
text, incomplete tool data, conflicting terminal states, and unknown reasons
remain fail-closed. SQLite schema v4 adds the nullable completion reason and
backfills existing completed Runs and their completion events as `stop`.

The production registry initially contains only explicitly composed read-only
tools. Local writes, external writes, destructive actions, shell access, MCP,
subagents, background work, memory, search, and file mutation are not implied by
the Agent loop and must be approved as separate capabilities later.

The core loop and registry boundary are now implemented independently of HTTP
and native Provider transports. The loop consumes only the Conversation
repository protocol, normalized Model gateway, and explicit Tool Registry. It
streams text into Run partial state, executes structured calls sequentially,
persists only bounded semantic summaries, and stops on duplicate failed calls,
round/tool limits, cancellation, malformed model output, or safe Provider
errors. The runtime will compose an empty registry until an individual read-only
tool is separately approved and implemented; the UI must not advertise tools
that are not present in that composition.

## Provider and response-mode boundary

The Model gateway presents one normalized stream to the Agent loop while each
adapter owns its native Provider request and response format. A Run keeps the
selected Provider, model id, and response mode fixed for its entire lifetime.

`default` omits an explicit reasoning-strength parameter. `fast`, `balanced`,
and `deep` map only when the selected Provider/model supports an equivalent
setting. Unsupported behavior must be reported accurately; it must not be
silently presented as applied.

The three native streaming adapters are now implemented behind the normalized
gateway:

- OpenAI uses `POST https://api.openai.com/v1/responses` with `store: false`.
- Anthropic uses `POST https://api.anthropic.com/v1/messages` with the fixed
  `anthropic-version: 2023-06-01` header.
- OpenRouter uses `POST https://openrouter.ai/api/v1/chat/completions` without
  attribution headers.

Every model round decrypts the selected credential only while holding the same
per-Provider operation lock used by connect, test, delete, and model discovery.
The key is never placed in a request body or retained by the gateway. Redirects
are disabled; connect/write/pool timeouts are 30 seconds, a model stream is
bounded to 300 seconds and 16 MiB, and one upstream SSE event is bounded to
1 MiB. Status, transport, timeout, malformed stream, duplicate JSON key, and
incomplete terminal failures are reduced to fixed safe inference errors.
Normal output-limit terminal reasons are instead preserved as successful but
explicitly truncated completions.

For explicit modes, OpenRouter receives `reasoning.effort` with reasoning output
excluded, OpenAI reasoning-capable models receive `reasoning.effort`, and
Anthropic receives `output_config.effort`; the values are low, medium, and high
for fast, balanced, and deep. `default` omits all three fields so the Provider
selects its own behavior. Reasoning/thinking stream fields are consumed only as
protocol data and never become Model events, Messages, Run events, logs, or
database content.

These adapters and the shared credential/lock composition are now connected to
the live Run workflow. The production Tool Registry remains empty, so native
requests do not advertise an unimplemented tool.

## HTTP and security boundary

`contracts/agent-chat.openapi.json` is authoritative. State-changing operations
remain subject to the existing exact same-origin policy. SSE is used because the
first workflow needs server-to-browser events only; it also retains the current
HTTP loopback security boundary.

The UI may display semantic status, safe errors, and tool summaries. It must not
display or persist API keys, encrypted credential material, raw Provider
responses, internal prompts, or hidden reasoning. The URL hash identifies a
conversation by backend UUID rather than by its title or message content.

Run start and cancel use the same exact loopback Host and same-origin Origin
middleware as Provider/settings mutations. SSE remains a GET under the loopback
Host boundary and is not exposed through CORS. Runtime startup marks any
pre-existing queued, running, or cancelling Run interrupted before binding the
Agent chat dependency. Shutdown first unbinds HTTP, then cancels owned tasks and
records interruption before closing the shared Provider HTTP client.

## Deliberate exclusions

This first boundary does not restore archived Task delegation, workflow state,
keyword routing, subagents, MCP, memory, search indexing, background processes,
file rollback, approval workflows, attachments, or database FTS. Each can be
designed later around the same Run, event, AppPaths, registry, and policy seams
when an approved user workflow needs it.
