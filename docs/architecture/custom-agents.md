# Custom Agents and child execution

## Definition boundary

Global definitions live under the AppPaths `agents_dir`; workspace definitions
live in the managed workspace's `agents` directory. Each definition is one TOML
file. Required fields are `name`, `description`, and `developer_instructions`;
optional `provider_id` and `model` must be supplied together. Unknown fields,
invalid encodings, oversized files, and unsafe path chains are rejected.
Credentials, scripts, tool grants, and sandbox configuration are not definition
fields. These files use OpenSprite's format, not arbitrary Codex configuration.

The versioned catalog tracks identity, scope, filename, revision and enabled
state. Workspace names shadow global names using NFC case-insensitive matching,
including disabled or unavailable local registrations. Invalid catalog data
disables delegation without preventing ordinary chat.

## Accepted execution snapshots

Chat acceptance resolves Workspace, Skills and Agent definitions under the
Workspace mutation gate. The Agent snapshot retains parsed definition contents
in memory. Later configuration edits do not change an accepted Run's roles.
The parent loop captures its tool registry, tool availability and base prompt
before adding internal discovery capabilities. Children receive that same
Workspace object and the captured tools; they do not resolve dynamic MCP tools
again. Child Skills keep the available snapshot but clear manual selections.

## Delegation flow

The main model receives bounded role discovery, not every full definition.
`discover_agents` pages descriptions. `spawn_agent` accepts an Agent ID and
bounded task/background/scope/expected-output fields, never a model, filesystem
path or permission override. `wait_agents`, `get_agent_result` and `cancel_agent`
enforce parent ownership. Result reads are limited to 4,000 characters per page.

`ChildAgentExecutor` composes the same Agent loop with a child context repository.
Its transcript contains the explicit delegation task, not the parent history.
The role is JSON-wrapped user-managed instruction content below system policy.
No delegation tools are attached to children and approval is prohibited. Skills
remain usable with ordinary tools disabled; they cannot enable those tools.

## Lifetime and storage

SQLite schema 15 stores child identity, model, status and result in
`agent_executions`, with bounded events in `agent_execution_events`. It creates
no sidebar conversation or parent message. Parent/spawn-call uniqueness and a
request hash enforce replay identity. Paths and definition bodies are not child
record columns. Explicit prompt logging follows the parent Run setting.

The task pool allows two running children per parent, four globally and six
created children per parent. The ten-minute deadline includes queue time.
Parents do not consume child semaphore slots. Completion waits for children;
cancellation and failure cancel and await them. Inputs and in-memory results
are released when the parent finishes. Startup interrupts unfinished persisted
children, without automatic replay. A deadline is distinct from user cancellation.

Acceptance is serialized with closing, but result waiting never holds the
acceptance lock. Failed pool admission compensates the durable queued record.
Observer persistence errors use a bounded retry and a safe failure code; parent
cleanup drains tasks and releases snapshots even when the store is unavailable.
Persisted active rows that cannot be updated during a database outage are
interrupted by normal startup recovery, not silently reported as completed.

## Verification status

Controlled model tests exercise discovery, spawning, waiting, result reads,
parent synthesis, isolation and parent cancellation through the shared loop.
Three configured-provider probe cases cover explicit delegation, discovery and
an unrelated negative case. They do not establish general automatic delegation
quality. Browser and platform evidence is recorded in change record 0224; real
Linux GUI/systemd execution remains outside the verified scope.
