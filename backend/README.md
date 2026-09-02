# Backend

This directory contains the Python 3.12-3.13 FastAPI foundation for the
local OpenSprite service. `contracts/provider-connections.openapi.json` and
`contracts/ai-settings.openapi.json` and
`contracts/general-settings.openapi.json` and
`contracts/conversation-settings.openapi.json` are the authoritative HTTP contracts.
MCP connections and per-call approvals are defined by
`contracts/mcp-connections.openapi.json` and `contracts/tool-approvals.openapi.json`.

The current slice provides:

- a typed ASGI `create_app()` factory;
- `GET /healthz`;
- thin provider-connection routes and public models;
- a fixed OpenAI/Anthropic/OpenRouter validation catalog using `httpx`;
- on-demand OpenRouter model discovery using the stored credential;
- strict persisted AI settings at `config/settings.json`, exposed through
  `GET`/`PUT /api/settings/ai`, covering model/context/output budgets,
  reasoning mode, output continuation, response delivery and full Prompt logs;
- strict persisted locale and time-zone settings at `config/general.json`,
  exposed through `GET`/`PUT /api/settings/general`;
- strict persisted startup, message sending, chat auto-scroll and execution-panel settings at
  `config/conversation.json`, exposed through
  `GET`/`PUT /api/settings/conversation`;
- official MCP Python SDK v2 Client sessions for explicitly configured local
  stdio or Streamable HTTP Servers with no authentication or a manually supplied
  Bearer token, with strict lazy schema-v3
  `config/mcp.json`, explicit lifecycle routes, bounded Tool discovery and a
  per-Run dynamic Tool snapshot;
- a user-initiated `POST /api/local-paths/pick` boundary that opens the Windows
  native file dialog or Linux XDG Desktop Portal without persisting or listing
  filesystem paths;
- short-lived, exact-argument, single-use MCP Tool approval plus required
  HMAC hash-chained receipts that omit raw arguments and results;
- a transactional `ProviderConnectionService` behind the injectable
  `ProviderConnections` seam;
- a synchronous, injectable AES-256-GCM credential store below `.opensprite`;
- a pure `AppPaths` contract rooted at `%USERPROFILE%\.opensprite` on Windows
  and `~/.opensprite` on Linux;
- strict non-secret provider metadata at `state/providers.json`, written by
  atomic JSON replacement;
- an explicit `create_provider_runtime()` composition factory;
- durable Conversation, Message, Run, rebuildable compaction and semantic event persistence in SQLite;
- one bounded dynamic System Prompt per Run using locale, time zone and current
  time, with a required full receipt below `.opensprite/logs/system-prompts`;
- one token-budgeted Agent loop with explicit recent-history retention,
  rebuildable older-history compaction, an explicit Tool Registry and normalized
  native Provider inference gateway;
- a secured `create_system_app()` runtime factory that owns and closes the
  provider HTTP client through FastAPI lifespan; and
- an injectable `create_app()` default that remains unchanged and fails closed
  with `credential_store_unavailable` unless a caller supplies dependencies.

It stores provider and MCP Bearer secrets only as AES-256-GCM ciphertext in `auth.json`, using
a random per-install key at `config/credential.key`. Windows and Linux share the
same format and do not require a startup password. This protects an isolated
`auth.json`, but not an attacker who obtains the complete `.opensprite` root
including its key. It does not contain an application CLI. Unit tests inject
`httpx.MockTransport` and temporary data
roots; they make no real provider request or credential operation.

Constructing `AppPaths`, importing this package, starting the system app, and
reading absent provider or credential state are filesystem-side-effect free.
The credential and key files are created only after a provider key validates or
an MCP Bearer configuration is explicitly saved;
the provider repository creates `.opensprite/state` when metadata is written.
The AI settings file is created only after a successful settings write. It uses
strict schema v8 and stores one nullable Provider/model identifier plus the
Context/output budgets, `default`/`fast`/`balanced`/`deep` reasoning mode,
`off`/`1`/`2`/`3`/`5`/`unlimited` output-continuation policy, `stream`/`complete`
response delivery preference and full-Prompt logging preference. `default`
means a future inference request must omit reasoning-strength parameters and
defer to the Provider. A missing file reads as a null model with stream delivery
and default mode without creating any directory. The file never contains a raw
API key, display label, or dynamic model catalog. Conversations, SQLite Runs,
semantic events, backend logs and Prompt receipts are implemented below the
same `.opensprite` root; uploads, outputs, memory and cache remain reserved until
their approved features write them.

The general settings file is created only after a successful PUT. It uses
strict schema v1 and is stored separately so locale and time-zone updates cannot
overwrite AI model configuration.

The conversation settings file is also created only after a successful PUT. It
uses independent strict schema v3 for startup, composer, chat auto-scroll and
execution-panel default behavior, so it cannot invalidate General Settings.
Current schema v2 reads with the panel collapsed and is rewritten only after a
successful PUT; schema v1 remains rejected.

The System Prompt log directory is created only when a Run reaches Prompt
construction. Each create-only Markdown receipt contains the exact trusted
Prompt sent to the Provider plus version, source and SHA-256 metadata. It does
not contain the user message, conversation history, credentials, Provider
response or hidden reasoning. A complete fsynced receipt is required before the
first Provider request for that Run.

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
keeps only text-input/text-output models with valid Context capability,
deduplicates by id, sorts by name then id, and returns at most 1000 entries. The
upstream response is capped at 4 MiB and is never written to `.opensprite`;
sanitized capabilities may be cached in process memory for ten minutes.

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
