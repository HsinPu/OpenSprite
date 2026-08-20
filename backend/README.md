# Backend

This directory contains the minimal Python 3.12+ FastAPI foundation for the
local OpenSprite service. `contracts/provider-connections.openapi.json` is the
authoritative HTTP contract.

The current slice provides:

- a typed ASGI `create_app()` factory;
- `GET /healthz`;
- thin provider-connection routes and public models;
- a fixed OpenAI/Anthropic validation catalog using `httpx`;
- a transactional `ProviderConnectionService` behind the injectable
  `ProviderConnections` seam;
- a synchronous, injectable OS credential-store boundary backed by `keyring`;
- strict non-secret provider metadata under the platform-local application data
  directory, written by atomic JSON replacement;
- an explicit `create_provider_runtime()` composition factory; and
- a default application dependency that still fails closed with
  `credential_store_unavailable` until a future server-launch slice injects the
  composed runtime.

It deliberately does not contain credential persistence outside Windows
Credential Manager or Linux Secret Service, a plaintext fallback, a database,
an Agent runtime, an application CLI, or server-launch lifecycle wiring. Unit
tests inject `httpx.MockTransport` and fake credential/state repositories; they
make no real provider request or operating-system credential call.

OpenAI validation calls `GET https://api.openai.com/v1/models` with an
`Authorization: Bearer` header. Anthropic validation calls
`GET https://api.anthropic.com/v1/models?limit=1` with `x-api-key` and
`anthropic-version: 2023-06-01`. Both use a fixed 30-second timeout, default TLS
verification, and disabled redirects. A success response must be a JSON object
with a `data` list and fit within the 1 MiB validation-body limit; the list is
never persisted.

Provider mutations are serialized per provider inside the single owning
desktop backend process. Candidate credentials are validated before any local
write. Secret and metadata writes are verified; partial failures restore and
re-read the prior secret and prior state before returning only the fixed
`credential_store_unavailable` error. POST test is a state-only transaction: it
reads but never writes or deletes the stored credential, including during
rollback. Metadata schema version 2 contains provider id, status, a display-only
preview, a UTC last-check time, and an internal full SHA-256 credential
fingerprint. The fingerprint binds metadata to the complete credential but is
never exposed in `ProviderSummary`. Schema version 1 is rejected with no
migration or fallback under the new-install policy.

`KeyringCredentialStore.from_system().preflight()` checks backend capability
without reading, writing, or deleting a credential. It accepts only keyring's
native `WinVaultKeyring` on Windows or `SecretService.Keyring` on Linux and
fails closed when selection fails, identity is overridden, the platform is
unsupported, or backend priority is not positive. Preflight does not prove
later read, write, unlock, or delete lifecycle usability; each operation still
fails closed independently.

After dependency synchronization, run the focused checks from this directory:

```powershell
uv sync --dev
uv run pytest
```
