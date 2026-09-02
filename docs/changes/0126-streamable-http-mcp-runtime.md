# Streamable HTTP MCP runtime

## Scope

- Add a fail-closed target policy for public HTTPS and loopback HTTP MCP
  endpoints, rejecting credentials, query strings, fragments, redirects,
  private/special addresses and invalid TLS.
- Dispatch the official MCP Python SDK Client through stdio or a restricted
  Streamable HTTP transport while preserving owner-task lifecycle, operation
  locks, bounded discovery, Tool calls and clean shutdown.
- Map authentication-required, blocked-target, TLS, redirect and protocol
  failures to fixed safe public errors.
- Reuse the existing per-Run Tool snapshot, per-call approval and HMAC receipt
  boundary without persisting HTTP credentials or response content.

## Verification

Repository-owned stateless HTTP fixtures cover negotiation, discovery,
cross-request lifecycle, Agent execution, exact-argument approval, receipt
privacy, HTTP 401 and redirect rejection alongside stdio regression tests.
The complete backend suite passed with 572 tests and 2 documented skips.
