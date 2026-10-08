# Agent chat architecture

## Accepted task

`AgentChatService` validates one text message and client request UUID, checks an existing accepted request before reading mutable settings, and snapshots the selected model, output/context settings, reasoning decision, Workspace, Provider endpoint and API v3 execution plugin.
Acceptance is durable and idempotent. The same request identity returns the existing Run; different content using that identity is rejected.
A Workspace mutation gate serializes acceptance against catalog/provider changes; one active Run per conversation is enforced by SQLite.

## Execution

`RunManager` owns asynchronous tasks and cancellation. `AgentLoop` prepares the system prompt and bounded history, records `execution.selected`, creates fresh plugin instances and delegates coordination to a Host.
`LoopExecutionHost` owns model requests, transcript, checkpoints, context retries, output continuation, semantic events, partial output and the only permitted final result.
The Driver sequentially calls `checkpoint`, `next_turn`, `finish` and returns the exact issued result.
Concurrent calls, modified/replayed turns, manufactured results and swallowed Host failures cannot produce successful Runs.
Cancellation preserves durable partial text; restart interrupts unfinished Runs rather than resuming hidden work.

## Context and inference

The authoritative capability resolver plans Context/output budgets. Older history may be summarized without deleting original messages.
Main, compaction and continuation attempts have bounded semantic diagnostics and schema-v2 text context receipts.
The core eligibility gates, cancellation and budgets apply before plugin recovery decisions; a plugin cannot add authority or increase limits.
Provider endpoints and reasoning choices stay fixed for an accepted task. Native OpenAI Responses, Anthropic Messages and OpenRouter/compatible Chat Completions stream text and usage.
Action/function/tool responses are rejected as `invalid_provider_response`; no action catalog, tool role or execution registry exists.

## Browser and persistence

The browser sends a text Run request, follows/replays SSE by original sequence and renders message text, execution state and model/compaction diagnostics.
No raw Provider payload, credential, system prompt or hidden reasoning is exposed.
SQLite v21 fresh data has five core tables. Existing v20 data is preserved; retired event types and incompatible execution/receipt records are omitted from the current read projection without rewriting stored rows.
See [clean-agent-core](clean-agent-core.md) and the authoritative `agent-chat.openapi.json` for upgrade and event boundaries.
