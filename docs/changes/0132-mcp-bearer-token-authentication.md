# MCP Bearer token authentication

## Objective

Streamable HTTP MCP connections now support either no authentication or one
manually supplied Bearer token. Create requests require the token, while update
requests may omit it to preserve the existing encrypted value.

## Changes

The MCP schema advances to v3 and stores only the authentication type. Existing
schema-v1 and schema-v2 records remain readable as no-authentication connections.
Bearer tokens use a server-id-derived credential identifier in the shared
AES-256-GCM `auth.json` store and never appear in `mcp.json`, public summaries,
confirmation dialogs, logs, or sanitized errors. Replacing or deleting a server
updates its credential with compensating rollback when the config write fails.

The settings editor exposes a password field only for Streamable HTTP Bearer
authentication. Saved tokens are represented by a configured boolean and are
never read back into the browser.

## Public impact

MCP create and update requests gain an `authentication` union. Server summaries
return only `none` or the non-secret Bearer configured state. A new sanitized
`credential_store_unavailable` error identifies encrypted-store failures.

## Verification

- Backend MCP, credential, contract, app, and runtime tests passed.
- Frontend MCP API and settings component tests passed.
- Full backend suite passed with 581 tests and 2 existing conditional skips;
  full frontend Vitest passed with 225 tests.

## Remaining work

OAuth authorization-code, client-credentials, API-key, custom-header, and
enterprise-managed authentication remain outside this slice.
