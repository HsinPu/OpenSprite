# 0031 - Native inference adapters

## Objective

Connect the bounded Agent core to OpenAI, Anthropic, and OpenRouter through
native, secret-safe, streaming HTTP adapters without adding chat HTTP routes.

## Changes

- Added separate OpenAI Responses, Anthropic Messages, and OpenRouter Chat
  Completions adapter modules behind the normalized Model gateway.
- Added bounded strict SSE and JSON parsing with duplicate-key rejection,
  redirect denial, fixed timeouts, total-stream and per-event limits, typed
  status mapping, explicit terminal validation, and safe malformed responses.
- Added native transcript and strict function-tool serialization plus streamed
  text, completed tool-call, token-usage, and completion normalization.
- Added capability-aware response-mode mapping: default omits effort; fast,
  balanced, and deep map to low, medium, and high in each Provider's native
  field. Explicit OpenAI effort is rejected before network use for a model that
  is not identified as reasoning-capable.
- Added on-demand encrypted credential reads and shared per-Provider locks. The
  same lock instance now serializes connection lifecycle, OpenRouter discovery,
  and one complete inference stream.
- Kept Provider reasoning/thinking fields out of normalized events and durable
  state; no raw secret, upstream body, tool argument, or hidden reasoning is
  persisted.

## Public impact

There is still no public chat route in this slice. Once composed by the later
Run API, the selected model can stream through all three configured Providers.
Provider connection, AI settings, and frontend payloads remain unchanged.

## Verification

- No-network tests verify exact URLs, auth headers, body formats, omitted default
  effort, all nine explicit effort mappings, native transcript/tool conversion,
  text/tool/usage/completion streams, and hidden-reasoning suppression.
- Failure tests cover missing/unavailable credentials, 401/403/429/5xx,
  redirects, transport timeout, missing SSE content type, oversized events,
  malformed streams, duplicate tool JSON, and unsupported explicit OpenAI
  effort.
- Integration testing runs the native OpenRouter gateway through the real Agent
  loop and SQLite repository and proves only visible text is stored.
- Existing Provider connection tests prove the injected operation lock is used
  and the runtime factory remains offline until an operation.
- The complete backend suite, Python compilation, dependency checks, CodeGraph,
  and whitespace checks run before commit.

## Remaining work

Compose the repository, settings, Agent, gateway, Run manager, HTTP routes, SSE
replay, and cancellation in the system runtime, then connect the frontend.
