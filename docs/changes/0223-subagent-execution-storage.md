# Subagent execution storage

- SQLite schema 15 introduces `agent_executions` and `agent_execution_events`.
- Child records reference their parent Run without creating sidebar conversations
  or adding messages to the parent's conversation.
- Parent/spawn-call uniqueness provides the durable idempotency boundary.
- Definition hashes and model identity are stored; definition instructions and
  workspace paths are not columns in child storage.
- Fresh database creation and the transactional v14 migration share the same
  table statements. Migration failure rolls back all newly created objects.
- Updated older migration fixtures to remove child tables before simulating
  databases predating this feature, rather than weakening production migration.

Verification: child schema and conversation repository tests: 41 passed.
The child repository now enforces parent ownership, durable replay, the six-child
creation limit and terminal-state preservation. Runtime startup interrupts
unfinished children after initializing/migrating the conversation database.
The runtime, child storage and initial task-pool suite passes 23 tests.
An isolated child context port now runs the existing Agent loop without reading
or writing parent messages. Controlled-model tests verify child completion and
output continuation, with results persisted separately. The loop accepts an
explicit approval prohibition for child execution.
Parent delegation is now composed into runtime: Agent definitions are captured
at Run acceptance, the model can discover/spawn/wait/read/cancel, and the child
executor reuses the shared loop with isolated history and no approval authority.
Parent completion waits for children; failure/cancellation cleans them up.
Terminal in-memory inputs are released after the owning parent finishes.
Controlled end-to-end parent/child tests and UI inspection are complete; real
provider probe evidence and final lifecycle hardening are recorded in 0224.
