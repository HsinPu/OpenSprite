# MCP Tools approval and settings

## Scope

- Extend each Run's base Tool Registry with one immutable snapshot from
  connected MCP Servers while preserving offline enabled ids.
- Treat every MCP Tool as sensitive and require `allow_once` or `deny` for each
  exact argument object. Raw arguments remain transient and are never written
  to Run events or receipts.
- Add bounded approval events, strict approval HTTP endpoints, SQLite schema v9,
  required HMAC-SHA-256 hash-chained receipts, and receipt verification.
- Add the real MCP Server settings UI, exact-command save/start confirmation,
  discovered Tool switches, and the Run approval card in Traditional Chinese,
  English and Japanese.

## Verification

- Dynamic Agent call, allow, deny, expiry/single-use, event privacy, no-start
  before approval, receipt creation and tamper-detection tests.
- Frontend strict API, command-confirmation, approval-card, i18n, settings and
  execution-panel tests.
- Full backend: 557 passed, 2 skipped. Full frontend: 217 passed. Typecheck,
  production build, compileall, offline lock check and dependency check passed.
- Installed-runtime browser smoke connected the repository-owned fixture,
  discovered two Tools, required exact-argument approval, executed `echo`,
  displayed its friendly name, and left no raw test value in the verified
  receipt chain. The fixture was then stopped and removed and Tool settings
  were restored to Calculator only.
