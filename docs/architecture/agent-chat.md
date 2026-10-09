# Agent chat architecture

## Accepted task

`AgentChatService` validates one text message and client request UUID, checks an existing accepted request before reading mutable settings, and snapshots the selected model, output/context settings, reasoning decision, Workspace, Provider endpoint and API v4 execution plugin.
Acceptance is durable and idempotent. The same request identity returns the existing Run; different content using that identity is rejected.
A Workspace mutation gate serializes acceptance against catalog/provider changes; one active Run per conversation is enforced by SQLite.

## Execution

`RunManager` owns asynchronous tasks and cancellation. `RunExecutor` prepares pinned context budgets/system prompt, creates a fresh selected Loop, and owns terminal transactions. Admission persists execution.selected before background execution.
`LoopExecutionHost` exposes single bounded context/infer/compact operations, cancellation, step persistence, answer streaming and validated final results. It does not decide retries, summary triggers or continuation.
The Loop sequentially calls checkpoint/context/infer/compact/finish and returns the exact issued result. Official policy lives in a separate opensprite-standard-loop wheel; external Loops can run draft/review/revision.
Concurrent calls, modified/replayed turns, manufactured results and swallowed Host failures cannot produce successful Runs.
Cancellation preserves durable partial text; restart interrupts unfinished Runs rather than resuming hidden work.

## Context and inference

The authoritative capability resolver plans Context/output budgets. Older history may be summarized without deleting original messages.
Main, compaction and continuation attempts have bounded semantic diagnostics and schema-v2 text context receipts.
Core cancellation, pinned model settings and hard limits apply to every operation. Loop chooses context ranges, prompts, recovery and continuation within these limits.
Provider endpoints and reasoning choices stay fixed for an accepted task. Native OpenAI Responses, Anthropic Messages and OpenRouter/compatible Chat Completions stream text and usage.
Action/function/tool responses are rejected as `invalid_provider_response`; no action catalog, tool role or execution registry exists.

## Browser and persistence

The browser sends a text Run request, follows/replays SSE by original sequence and renders message text, execution state and model/compaction diagnostics.
No raw Provider payload, credential, system prompt or hidden reasoning is exposed.
SQLite v22 fresh data has six core tables including run_steps. Existing v20/v21 data is transactionally preserved; retired event types and incompatible execution/receipt records are omitted from the current read projection without rewriting stored rows.
See [clean-agent-core](clean-agent-core.md) and the authoritative `agent-chat.openapi.json` for upgrade and event boundaries.

Draft step text is returned only by same-origin /api/runs/{run_id}/steps. Semantic step events contain labels/status/usage. Only answer text enters conversation messages; restart interrupts unfinished steps.
