# Agent chat architecture

## Purpose

OpenSprite treats each submitted user message as one bounded agent run. Every
message enters the same path; there is no keyword classifier, legacy Task
lifecycle, or alternate direct-to-model branch.

```text
Browser UI
  -> Conversation and Run HTTP API
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
  model, response mode, status, safe error, partial assistant text, and timing.
- A **Run event** is a small durable semantic projection used for replay and UI
  status. Events never contain credentials, raw upstream bodies, or hidden
  chain-of-thought.
- A **Tool call** is an in-memory step inside a run. Only its safe name, status,
  and bounded public summary may become a Run event.

The dependency direction is fixed:

```text
API -> Agent -> Inference
          |  -> Tools
          `-> Conversations
```

`Conversations` must not import Provider adapters. `Tools` must not import the
Agent loop. Provider adapters perform no persistence. The API composes these
boundaries but does not implement model or tool behavior.

## Public workflow

1. `POST /api/runs` receives a nullable conversation id, a client-generated
   request id, and one non-empty user message.
2. Backend settings select one connected Provider and model. The message,
   conversation, and queued Run are committed in one SQLite transaction.
3. The Run manager starts the bounded Agent loop after the durable start
   transaction succeeds.
4. The browser opens `GET /api/runs/{run_id}/events`. Persisted events replay in
   sequence and then stream over SSE; reconnect uses `Last-Event-ID`.
5. Text deltas update the Run partial text and UI. A final answer creates one
   durable assistant Message and completes the Run atomically.
6. A structured model tool request must match an explicitly registered tool and
   pass policy before execution. Tool output returns to the same Agent loop.
7. Cancellation, limits, Provider failure, or shutdown move the Run to an
   explicit terminal state. They do not fabricate an assistant success message.

The request id is the idempotency boundary for retries. A conversation may have
only one queued, running, or cancelling Run. A new conversation is created only
when the first user message is durably accepted.

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
- duplicate failed calls stop instead of retrying forever;
- each tool has an explicit timeout and output cap;
- cancellation is checked before model and tool boundaries.

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

For explicit modes, OpenRouter receives `reasoning.effort` with reasoning output
excluded, OpenAI reasoning-capable models receive `reasoning.effort`, and
Anthropic receives `output_config.effort`; the values are low, medium, and high
for fast, balanced, and deep. `default` omits all three fields so the Provider
selects its own behavior. Reasoning/thinking stream fields are consumed only as
protocol data and never become Model events, Messages, Run events, logs, or
database content.

These adapters and the shared credential/lock composition exist now, but live
chat HTTP routes are still a later slice. The production Tool Registry remains
empty, so no native request currently advertises an unimplemented tool.

## HTTP and security boundary

`contracts/agent-chat.openapi.json` is authoritative. State-changing operations
remain subject to the existing exact same-origin policy. SSE is used because the
first workflow needs server-to-browser events only; it also retains the current
HTTP loopback security boundary.

The UI may display semantic status, safe errors, and tool summaries. It must not
display or persist API keys, encrypted credential material, raw Provider
responses, internal prompts, or hidden reasoning. The URL hash identifies a
conversation by backend UUID rather than by its title or message content.

## Deliberate exclusions

This first boundary does not restore archived Task delegation, workflow state,
keyword routing, subagents, MCP, memory, search indexing, background processes,
file rollback, approval workflows, attachments, or database FTS. Each can be
designed later around the same Run, event, AppPaths, registry, and policy seams
when an approved user workflow needs it.
