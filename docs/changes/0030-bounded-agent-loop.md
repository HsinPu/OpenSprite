# 0030 - Bounded Agent loop

## Objective

Implement one bounded execution path for every accepted user message, with a
normalized model seam and an explicitly governed structured-tool boundary.

## Changes

- Added Provider-neutral model requests, transcripts, text deltas, completed
  tool calls, usage, completion reasons, and typed safe gateway failures.
- Added the Agent loop with a fixed system prompt, 100-message history cap,
  eight-model-round cap, sixteen-tool-call cap, duplicate-failure stop, partial
  text persistence, semantic events, safe completion/failure, and cancellation.
- Added a Run manager that owns one asyncio task and cancellation signal per
  active Run and marks abandoned work interrupted during shutdown.
- Added strict tool definitions, a bounded JSON-schema subset, exact argument
  validation, effect classification, default read-only policy, execution
  timeout, output cap, safe error mapping, and explicit registry composition.
- Kept the runtime registry empty until a concrete read-only tool is separately
  approved; no shell, file mutation, search, MCP, memory, or subagent capability
  was introduced.
- Added AST dependency guards so Agent code cannot import SQLite or Provider
  adapters, inference cannot import persistence/tools/runtime, and tools cannot
  import Agent/inference/persistence/Provider modules.

## Public impact

No HTTP route or live Provider inference request is added in this slice. The new
core can be exercised with injected gateways and tools. Only visible assistant
text and safe semantic tool status/summary events may be persisted; tool
arguments, raw tool output, hidden reasoning, and Provider payloads are not Run
events.

## Verification

- Tool tests cover explicit registration, strict arguments, unknown tools,
  write denial, timeout, oversized output, duplicate names, and loose schemas.
- Agent tests cover direct final text, a two-round structured tool call, safe
  Provider failure, duplicate failed calls, round limits, and blocked-stream
  cancellation.
- Run-manager tests cover duplicate task prevention, user cancellation, normal
  completion, and shutdown interruption.
- Architecture tests enforce the intended dependency direction.
- The complete backend test suite, Python compilation, dependency checks, and
  whitespace checks run before commit.

## Remaining work

Implement native OpenRouter, OpenAI, and Anthropic inference transports, compose
the Run API/SSE lifecycle, and replace the frontend demo chat with real data.
