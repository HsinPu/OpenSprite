# Backend

This directory contains the minimal Python 3.12+ FastAPI foundation for the
local OpenSprite service. `contracts/provider-connections.openapi.json` and
`contracts/ai-settings.openapi.json` are the authoritative HTTP contracts.

The current slice provides:

- a typed ASGI `create_app()` factory;
- `GET /healthz`;
- thin provider-connection routes and public models;
- a fixed OpenAI/Anthropic/OpenRouter validation catalog using `httpx`;
- on-demand OpenRouter model discovery using the stored credential;
- strict persisted AI settings at `config/settings.json`, exposed through
  `GET`/`PUT /api/settings/ai`;
- a transactional `ProviderConnectionService` behind the injectable
  `ProviderConnections` seam;
- a synchronous, injectable AES-256-GCM credential store below `.opensprite`;
- a pure `AppPaths` contract rooted at `%USERPROFILE%\.opensprite` on Windows
  and `~/.opensprite` on Linux;
- strict non-secret provider metadata at `state/providers.json`, written by
  atomic JSON replacement;
- an explicit `create_provider_runtime()` composition factory;
- a secured `create_system_app()` runtime factory that owns and closes the
  provider HTTP client through FastAPI lifespan; and
- an injectable `create_app()` default that remains unchanged and fails closed
  with `credential_store_unavailable` unless a caller supplies dependencies.

It stores provider secrets only as AES-256-GCM ciphertext in `auth.json`, using
a random per-install key at `config/credential.key`. Windows and Linux share the
same format and do not require a startup password. This protects an isolated
`auth.json`, but not an attacker who obtains the complete `.opensprite` root
including its key. It does not contain a database, an Agent runtime or an
application CLI. Unit tests inject `httpx.MockTransport` and temporary data
roots; they make no real provider request or credential operation.

Constructing `AppPaths`, importing this package, starting the system app, and
reading absent provider or credential state are filesystem-side-effect free.
The credential and key files are created only after a provider key validates;
the provider repository creates `.opensprite/state` when metadata is written.
The AI settings file is created only after a successful settings write. It uses
strict schema v2 and stores one nullable Provider/model identifier plus the
`fast`, `balanced`, or `deep` response mode. A missing file reads as a null model
with balanced mode without creating any directory. The file never contains a
raw API key, display label, or dynamic model catalog. Database, conversation,
log, and cache paths remain reserved by the layout contract and are not created
before an approved feature uses them.

Importing or calling `create_system_app()` performs no credential file
operation or provider request. Each successful FastAPI lifespan
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

`GET /api/settings/ai` reads the confirmed model and response mode without
creating a file, decrypting a credential, or calling a provider. `PUT
/api/settings/ai` atomically replaces both values. A non-null model requires a
currently connected Provider; a null model remains valid and keeps the supplied
response mode. The operation does not perform model discovery, so a temporarily
unavailable OpenRouter catalog does not erase a saved model ID. Provider
metadata remains the only connection check; raw credentials are never read by
the settings API.

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

`EncryptedJsonCredentialStore` accepts only the three fixed providers in strict
schema version 1. Each secret uses a fresh 12-byte nonce and AAD binding the
schema, provider id and full fingerprint. Reads are bounded to 1 MiB; malformed
JSON, missing keys, altered ciphertext or failed authentication fail closed.
Both files use fsync and atomic replacement. Linux applies `0700` directories
and `0600` files; Windows relies on the user-profile ACL. Provider listing reads
only the encrypted entry fingerprint and does not decrypt the API key.
Its process-local lock protects cross-provider read-modify-write operations in
the one owning desktop backend. Do not run multiple Uvicorn workers, reloaders,
or concurrent backend processes against the same `.opensprite` root.

After dependency synchronization, run the focused checks from this directory:

```powershell
uv sync --dev
uv run pytest
```
