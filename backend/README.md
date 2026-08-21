# Backend

This directory contains the minimal Python 3.12+ FastAPI foundation for the
local OpenSprite service. `contracts/provider-connections.openapi.json` is the
authoritative HTTP contract.

The current slice provides:

- a typed ASGI `create_app()` factory;
- `GET /healthz`;
- thin provider-connection routes and public models;
- a fixed OpenAI/Anthropic/OpenRouter validation catalog using `httpx`;
- on-demand OpenRouter model discovery using the stored credential;
- a transactional `ProviderConnectionService` behind the injectable
  `ProviderConnections` seam;
- a synchronous, injectable OS credential-store boundary backed by `keyring`;
- a pure `AppPaths` contract rooted at `%USERPROFILE%\.opensprite` on Windows
  and `~/.opensprite` on Linux;
- strict non-secret provider metadata at `state/providers.json`, written by
  atomic JSON replacement;
- an explicit `create_provider_runtime()` composition factory;
- a secured `create_system_app()` runtime factory that owns and closes the
  provider HTTP client through FastAPI lifespan; and
- an injectable `create_app()` default that remains unchanged and fails closed
  with `credential_store_unavailable` unless a caller supplies dependencies.

It deliberately does not contain credential persistence outside Windows
Credential Manager or Linux Secret Service, a plaintext fallback, a database,
an Agent runtime or an application CLI. Unit
tests inject `httpx.MockTransport` and fake credential/state repositories; they
make no real provider request or operating-system credential call.

Constructing `AppPaths`, importing this package, starting the system app, and
reading absent provider state are filesystem-side-effect free. The provider
repository creates only `.opensprite/state` when metadata is first written.
Configuration, database, conversation, log, and cache paths are reserved by the
layout contract but are not created before an approved feature uses them.

Importing or calling `create_system_app()` performs no keyring selection,
credential operation, or provider request. Each successful FastAPI lifespan
entry creates and binds one fresh provider runtime. Teardown first replaces the
bound dependency with the fail-closed unavailable implementation, then closes
that entry's client exactly once. Startup failure never binds a runtime;
shutdown failure remains unbound and does not prevent a later fresh entry.
Concurrent lifespan entry is rejected before a second runtime can serve.

## Local server

Start the system application only on IPv4 loopback and disable proxy-header
interpretation:

```powershell
uv run uvicorn opensprite_backend.runtime:create_system_app --factory --host 127.0.0.1 --port 8765 --no-proxy-headers
```

The secured runtime rejects requests unless exactly one `Host` identifies
`localhost`, `127.0.0.1`, or bracketed `::1`. `POST`, `PUT`, `PATCH`, and
`DELETE` additionally require exactly one `Origin` whose canonical scheme,
host, and effective port equal the request scheme and `Host`. It does not trust
`X-Forwarded-*`, enable CORS, or fall back to `Referer`.

For the Vite development proxy, preserve the browser-facing `Host` and
`Origin` with `changeOrigin: false`. Both values must remain the same origin,
including the port; the backend does not allow an arbitrary second localhost
port. The documented uvicorn process must not be launched with proxy-header
support or a non-loopback bind.

OpenAI validation calls `GET https://api.openai.com/v1/models` with an
`Authorization: Bearer` header. Anthropic validation calls
`GET https://api.anthropic.com/v1/models?limit=1` with `x-api-key` and
`anthropic-version: 2023-06-01`. OpenRouter validation calls
`GET https://openrouter.ai/api/v1/key` with an `Authorization: Bearer` header
only. All three use a fixed 30-second timeout, default TLS verification, and
disabled redirects. OpenAI and Anthropic require a JSON `data` list;
OpenRouter requires a JSON `data` object. Every success response must fit within
the 1 MiB validation-body limit and no response content is persisted.

Connected OpenRouter accounts can load their available text models through
bodyless `POST /api/providers/openrouter/models`. The backend calls
`GET https://openrouter.ai/api/v1/models/user` with the stored Bearer credential,
keeps only text-input/text-output models, deduplicates by id, sorts by name then
id, and returns at most 1000 entries. The upstream response is capped at 4 MiB
and is never cached or written to `.opensprite`.

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
