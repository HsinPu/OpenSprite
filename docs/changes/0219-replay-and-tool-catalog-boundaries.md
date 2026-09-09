# Replay and tool catalog boundaries — 0.19.3

Accepted-request lookup now precedes mutable model, Provider, Workspace and
Skills resolution for user and scheduled Runs. It validates the same request
fingerprint as transactional creation. Existing results are returned without
starting another task or resolving a replacement snapshot. Transactional
creation retains its unique identity check for concurrent submissions.

Conflicting identities return HTTP 409 `idempotency_conflict`, with matching
frontend parsing and localized messages. Authentication remains unchanged.

Remove the 64-item model.started toolNames cap from storage, browser validation
and OpenAPI. Names remain format-checked, unique and sorted. MCP discovery caps,
Context budgeting and tool-call iteration limits are unchanged. No schema or
user-data migration is required.

Regression evidence: before implementation, configuration replay and 65/128-tool
cases failed (5 failures, one 64-tool control passed). After implementation,
service/repository tests pass (52); frontend API tests pass (12), typecheck passes.
Full backend verification: 862 passed, 3 skipped. Full frontend: 363 passed;
after adding the explicit HTTP conflict regression, all 13 API tests passed.
The updated service assertions also passed independently (14 tests).
Typecheck/production build, compileall, offline lock and dependency checks passed.
Existing bundle-size and jsdom pseudo-element warnings remain. SymbolLattice
reported a fresh index. No real MCP, paid-model or browser-disconnection test,
Linux execution, push or installed-runtime update is claimed.
