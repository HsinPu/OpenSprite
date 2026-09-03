# Local owner authentication

## Objective

Require one local-owner password and an in-memory backend session before
OpenSprite exposes conversations, settings, providers, MCP, runs, or tools.

## Changes

- Added strict Argon2id access/bootstrap stores, one-time setup, login
  throttling, process-memory sessions, password replacement, logout, and
  logout-all APIs.
- Added default-deny API middleware after the existing Host/Origin boundary and
  added CSP, anti-framing, no-sniff, no-referrer, and no-store headers.
- Added a three-language responsive AuthGate, login/setup screens, shared 401
  handling, SSE authentication rechecks, sidebar logout, and operational
  Privacy settings.
- Added Windows first-install bootstrap and explicit `-ResetLocalAccess`
  recovery while preserving unrelated user data.
- Added an authoritative OpenAPI contract and authentication architecture
  record.

## Public impact

New and upgraded installed runtimes require password setup/login. The canonical
browser URL is now `http://localhost:8765`; the service still binds only
`127.0.0.1`. Six `/api/auth/*` endpoints are added and all other `/api` routes
require the Secure HttpOnly session cookie.

## Verification

- Focused backend authentication, app contract, runtime, and installed-runtime
  tests.
- Frontend AuthGate, existing App/API, localization, and Settings tests.
- TypeScript typecheck and PowerShell parser validation.

## Remaining work

Data-at-rest encryption for SQLite, logs, and the existing credential files is
not included. Authentication does not defend against the same OS account or an
Administrator/root attacker.
