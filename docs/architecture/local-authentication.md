# Local authentication

OpenSprite requires one local-owner password before mounting the application or
serving any sensitive API. This boundary is intentionally not an account or
role system: there is no username, email address, cloud identity, multi-user
authorization, OAuth, MFA, or passkey flow.

## Stored and process-local state

`config/access.json` stores only a strict versioned Argon2id password hash. The
password is normalized with Unicode NFC and must contain 15–128 characters.
Argon2id currently uses 19 MiB of memory, two iterations, parallelism one, a
16-byte salt, and a 32-byte hash. Successful login opportunistically replaces a
hash if the configured parameters later change.

The browser receives a random 256-bit token in the
`__Host-OpenSpriteSession` Secure, HttpOnly, SameSite=Strict cookie. The backend
keeps only its SHA-256 digest in process memory. Sessions expire after 12 hours
of inactivity and are lost on backend restart, logout, logout-all, and password
replacement. Session state is never written to browser storage or disk.

This protects against unauthenticated access through the local HTTP surface. It
does not protect against malware running as the same operating-system account,
Administrator/root access, or direct reads of the existing SQLite database,
logs, and provider/MCP credential files.

## Request boundary

The existing loopback Host and same-origin mutation checks wrap authentication.
Static frontend files, `/healthz`, `/api/app-info`, `/api/auth/status`,
`/api/auth/setup`, and `/api/auth/login` are public. Every other `/api` route is
default-deny, including run SSE and tool approvals. Missing or expired sessions
receive `401 authentication_required`; throttled logins receive `429
rate_limited` and `Retry-After`.

Every HTTP response receives a no-store cache policy, a same-origin CSP with
framing disabled, `X-Content-Type-Options: nosniff`, and `Referrer-Policy:
no-referrer`. The browser-facing canonical URL is `http://localhost:8765`; the
backend continues binding only `127.0.0.1`.

## Setup and recovery

On a new install, the Windows installer creates a random one-time bootstrap
token. Only its SHA-256 digest and 30-minute lifetime are atomically stored in
`state/access-bootstrap.json`; the raw token exists only in the setup URL
fragment and is cleared from the address bar as soon as the frontend reads it.
Successful setup creates `access.json`, deletes the bootstrap record, and
issues the first session.

An upgrade preserves an existing `access.json`. The explicit installer switch
`-ResetLocalAccess` stops the old backend through the normal installer cutover,
replaces only the access/bootstrap state, and opens a new one-time setup link.
It does not remove conversations, settings, credentials, databases, or logs.

## Frontend lifecycle

`AuthGate` checks public authentication status before mounting `App`, so no
conversation, settings, provider, MCP, run, or tool request starts while logged
out. A shared HTTP boundary converts any later protected 401 into an immediate
App unmount. EventSource failures recheck authentication status so an expired
session is distinguished from a general connection failure. The requested chat
or new-chat hash remains intact across ordinary login.
