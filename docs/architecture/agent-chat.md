# Agent chat architecture

## Purpose

OpenSprite treats each submitted user message as one bounded agent run. Every
message enters the same path; there is no keyword classifier, legacy Task
lifecycle, or alternate direct-to-model branch.

```text
Browser UI
  -> Workspace-scoped Conversation and Run HTTP API
  -> Application orchestration + immutable Workspace snapshot
  -> Run manager
  -> Agent loop
     -> Model gateway -> one Provider adapter
     -> Tool registry -> policy -> explicitly registered tool
  -> SQLite conversation store
  -> semantic Run events -> SSE -> Browser UI
```

## Domain ownership

- A **Conversation** is a durable user-visible thread.
  It belongs to exactly one Workspace and carries an optimistic revision.
- A **Message** is durable visible user or assistant content. Internal prompts,
  raw Provider payloads, tool arguments, secrets, and hidden reasoning are not
  messages.
- A **Run** is the execution caused by one user message. It snapshots Provider,
  model, response mode, Context budget, status, completion reason, safe error,
  partial assistant text, timing, and Workspace identity. SQLite keeps only the
  Workspace ID, revision, name snapshot and nullable root hash; the canonical
  path stays in the in-memory execution context. Context budget remains internal
  and does not expand the public Run payload.
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

1. `POST /api/runs` receives a required Workspace id, nullable conversation id,
   client-generated request id, and one non-empty user message.
2. The application resolves one immutable Workspace execution context, verifies
   an existing Conversation has the same owner, and selects one connected
   Provider and model. The message, Conversation and queued Run are committed in
   one SQLite transaction.
3. The Run manager starts the bounded Agent loop after the durable start
   transaction succeeds.
4. The loop resolves the selected model capability, converts the Run's Context
   policy into an input budget, retains the recent message floor, and compacts
   only older history when required. It reads history in bounded 200-message
   pages and keeps paging until the token budget is covered; the page size is
   not a total history or compaction-count limit.
5. The browser opens `GET /api/runs/{run_id}/events`. Persisted events replay in
   sequence and then stream over SSE; reconnect uses `Last-Event-ID`. Live
   readers wait on a process-local post-commit notification and retain a long
   timeout fallback for changes made outside the current runtime.
6. Text deltas update the Run partial text and UI. A natural stop completes the
   Run. An output limit may enter the Run-snapshotted continuation policy;
   every attempt appends to the same Run and eventual assistant Message.
7. A structured model tool request must match an explicitly registered tool and
   pass policy before execution. Tool output returns to the same Agent loop.
8. Cancellation, limits, Provider failure, or shutdown move the Run to an
   explicit terminal state. They do not fabricate an assistant success message.

The request fingerprint includes the Workspace id, and the request id is the
idempotency boundary for retries. A conversation may have
only one queued, running, or cancelling Run. A new conversation is created only
when the first user message is durably accepted into the requested Workspace.
The application passes the exact accepted `WorkspaceExecutionContext` through
RunManager to AgentLoop. AgentLoop validates its identity against the durable
Run once and does not query the mutable Workspace catalog again.

This workflow is now composed in the local system runtime. `AgentChatService`
reads the atomic AI setting, verifies the selected Provider still has encrypted
credential metadata, commits the user Message and Run, and only then asks
`RunManager` to schedule execution. The API layer validates and serializes the
contract but does not call a Provider, execute a tool, or write SQLite directly.

At Run start, the injected System Prompt provider renders one trusted snapshot
from the confirmed locale, time-zone setting, current time and delimited
untrusted Workspace metadata. The exact same snapshot is used for every model
round in that Run. Before the first Provider
request, a complete create-only Prompt receipt must be fsynced below
`.opensprite/logs/system-prompts`; logging failure prevents the Provider call.

| Route | Responsibility |
| --- | --- |
| `GET /api/conversations?workspaceId=...` | Reverse-updated cursor page scoped to one Workspace. |
| `GET /api/conversations/{id}` | Resolve Conversation metadata and owning Workspace for a deep link. |
| `PUT /api/conversations/{id}/workspace` | Optimistically move an idle normal Conversation. |
| `GET /api/conversations/{id}/messages` | Visible Message page in ascending sequence. |
| `POST /api/runs` | Idempotently accept one Workspace-bound user message and queued Run. |
| `GET /api/runs/{id}` | Read the durable snapshot, partial text, completion reason, status, and safe error. |
| `GET /api/runs/{id}/events` | Replay and follow events after `Last-Event-ID`. |
| `POST /api/runs/{id}/cancel` | Bodyless cancellation of queued or running work. |

SSE frame ids are durable positive event sequences and frame event names equal
the semantic event type. Opening after completion replays the missing suffix and
closes. The browser closes its EventSource after receiving a terminal event.

## Browser workflow

The sidebar reads `GET /api/conversations` for the active Workspace and identifies a selected
conversation only by its backend UUID in the URL hash. A new conversation has
no durable identity until `POST /api/runs` accepts its first message; the
returned conversation UUID then replaces the temporary new-chat state.
Opening a `#chat=<uuid>` deep link first resolves its metadata; when its owner is
not active, the browser updates the backend catalog selection before loading the
Workspace-scoped Conversation list. Active Workspace state is not persisted in
browser storage.

The browser keeps the submitted user message visible while acceptance is in
flight, follows named semantic events over SSE, and appends only
`assistant.delta` text to the live assistant surface. At a terminal event it
reloads both the durable Run snapshot and visible Messages rather than treating
the stream buffer as authoritative. Duplicate replayed event sequences and
events belonging to an obsolete selected conversation are ignored. An active
Run exposes a stop action through the bodyless cancellation operation.

High-frequency assistant deltas are accumulated in the frontend and committed
to React state at most once per animation frame. Semantic execution events are
flushed before the next non-delta or terminal event, so execution ordering and
complete-response delivery remain unchanged. Persisted Markdown messages use a
stable memoized renderer; only the live message is re-parsed while it changes.

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
The base production Tool Registry contains the read-only `calculator`. At Run
start the Agent adds one immutable snapshot of supported Tools from currently
connected stdio or Streamable HTTP MCP Servers. The UI localizes the stable built-in id and
uses the discovered MCP display name for MCP events; it does not advertise a
capability unless an active Server actually provides it.
Every ToolContext carries the same immutable Workspace execution context used by
the Agent loop. Existing tools do not gain filesystem access from that metadata;
a future path-dependent tool must check availability and fail closed.

The Tools settings page reads the production catalog from `GET /api/tools` and
persists the global switch plus enabled tool ids through
`GET/PUT /api/settings/tools`. Tool settings live in
`.opensprite/config/tools.json`, separate from AI and conversation settings.
Each Run resolves one immutable availability snapshot before Context assembly.
Only definitions in that snapshot are advertised to the model, and the Registry
checks the same snapshot again before invocation. Changes therefore apply to
new Runs without changing an active Run. Historical events remain readable.
MCP ids enabled earlier remain in this settings file while their Server is
offline. They become available again only after that Server reconnects and
rediscovers the same canonical Tool id.

Configured MCP Servers are owned by the `/api/mcp/servers` CRUD surface,
explicit `test`, `start`, and `stop` operations, and per-Server Tool discovery.
The strict schema-v3 config lives at `.opensprite/config/mcp.json`; schema-v1
and schema-v2 records remain readable as no-authentication connections until the
next write. Local `stdio` plus no-authentication or manual-Bearer Streamable HTTP
are implemented. Bearer secrets remain encrypted in `auth.json` and never enter
the MCP config, public response, prompt log, or runtime log. A new or edited configuration is inert and disabled;
the browser displays the exact executable and argument vector before saving
and asks again before an explicit start. The backend invokes the absolute
executable directly without a shell. Startup launches only Servers previously
enabled by an explicit start and marked `startOnLaunch`.

Streamable HTTP accepts public HTTPS endpoints and loopback HTTP only. It
rejects credentials, query strings, fragments, redirects, private or special
network destinations, and invalid TLS certificates. Its restricted HTTP client
does not inherit proxy environment configuration. Manually supplied Bearer
authentication is the only supported HTTP credential; OAuth, arbitrary headers,
LAN targets, SSE and WebSocket remain outside the current contract.

## Persistence

The first implementation uses five SQLite tables under
`.opensprite/data/opensprite.db`:

- `conversations`
- `messages`
- `conversation_compactions`
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

Context is primarily bounded by tokens, with a defensive maximum of 256 model
messages and bounded 200-message repository pages for compaction. Normal Runs
do not impose a fixed number of compaction batches; an explicit provider-limit
retry still requests at most one additional compaction. `auto`,
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
SQLite migration history converts the former boolean to `2` or `off`; schema
v10 expands the bounded policy values while preserving Messages, Runs and events. The
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

The local runtime creates one `RunEventNotifier` alongside the SQLite
repository. Successful event and Run-state commits signal that notifier after
the transaction closes. `AgentChatService` drains persisted events immediately,
then waits for the next signal instead of repeatedly querying SQLite; a bounded
fallback wait preserves recovery if an external writer ever bypasses the
notifier. The notifier is process-local and does not change the HTTP/SSE
contract or SQLite schema.

The Agent checks the shared assistant-output limit before every durable delta,
so a Provider cannot push the SQLite Run beyond its storage contract. If an
otherwise recoverable repository write fails during background execution, the
Run manager makes one fail-closed terminal transition with a safe internal
error; it does not silently discard the task while leaving an active Run.
Each persisted assistant delta is also split on the encoded UTF-8 event-payload
boundary, so a multi-byte chunk cannot exceed SQLite's 64 KiB semantic-event
limit while the Run's durable partial text remains the complete response. The
Agent coalesces fast upstream text chunks into approximately 4K-character
batches before opening a SQLite write transaction, and flushes at model-round,
tool, terminal, error, and cancellation boundaries so event order and partial
text durability are preserved.

Automatic continuation is owned by the backend Agent loop, not by the browser.
The finite policies are 1, 2, 3, 5, 10, 20, or 50 continuation requests;
new settings default to 5 while existing saved settings and Run snapshots remain unchanged.
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

The base registry contains explicitly composed read-only tools. Its first tool
is `calculator`, which evaluates a 256-character arithmetic
expression through a bounded Python AST and Decimal whitelist. It permits only
decimal numbers, parentheses, unary signs, `+`, `-`, `*`, `/`, `//`, `%`, and
bounded integer powers. It does not use `eval`, execute code, or access files,
the shell, network, credentials, or user data. Local writes, external writes,
destructive actions, shell access, subagents, background work, memory, search,
and file mutation are not implied by the Agent loop.

Every MCP Tool is treated as sensitive regardless of its untrusted annotation.
Before each call, the Agent appends a bounded `tool.approval_requested` event
with ids, display name, argument hash and expiry, but no raw arguments.
`GET /api/tool-approvals/{id}` exposes exact arguments only from short-lived
process memory; `PUT` accepts only `allow_once` or `deny`. An allow is
single-use, exact-argument scoped, expires after ten minutes, and never becomes
a remembered policy. No `tool.started` event occurs before approval. Authorized
calls require an fsynced HMAC-SHA-256 hash-chained receipt under
`logs/tool-receipts/<local-date>.jsonl`, signed with the random local
`config/tool-receipt.key`. New version-3 receipts include Workspace availability
beside its ID, revision and root hash; the verifier preserves signed version-1
and version-2 history. Receipts never contain the absolute Workspace root, raw
arguments, results, credentials, or MCP stderr.

The core loop and registry boundary are now implemented independently of HTTP
and native Provider transports. The loop consumes only the Conversation
repository protocol, normalized Model gateway, and explicit Tool Registry. It
streams text into Run partial state, executes structured calls sequentially,
persists only bounded semantic summaries, and stops on duplicate failed calls,
round/tool limits, cancellation, malformed model output, or safe Provider
errors. The runtime composes the approved Calculator and extends it only with
the per-Run connected MCP snapshot; the UI must not advertise tools outside
those explicit sources.

The `model.started` semantic event records the sorted tool ids advertised for
that model request. It never records tool arguments or tool results. A disabled
tool cannot be executed even if a Provider returns an unsolicited call for it.

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
the live Run workflow. Native requests advertise only the Calculator definition
from the explicit production Tool Registry. Explicit OpenRouter model requests
also set `provider.require_parameters=true`, so a routed provider may not
silently ignore the requested tool-calling parameters. The `openrouter/auto`
router omits this extra Provider filter and selects a compatible upstream model
from the request features itself.

Rejected upstream responses write only the numeric HTTP status to the central
runtime log. Timeout and transport failures write only a stable failure label
and exception type. Response bodies, request bodies, prompts, URLs, headers,
and credentials are never included in these diagnostics.

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

This boundary does not restore archived Task delegation, keyword routing,
subagents, memory, search indexing, filesystem/Git/terminal tools, external
channel adapters, file rollback, attachments, or database FTS. Each can be
designed later around the same Run, event, Workspace snapshot, AppPaths,
registry and policy seams when an approved user workflow needs it.
