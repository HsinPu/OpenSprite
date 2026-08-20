# Backend

This directory contains the minimal Python 3.12+ FastAPI foundation for the
local OpenSprite service. `contracts/provider-connections.openapi.json` is the
authoritative HTTP contract.

The current slice provides:

- a typed ASGI `create_app()` factory;
- `GET /healthz`;
- thin provider-connection routes and public models;
- an explicit `ProviderConnections` dependency seam;
- a synchronous, injectable OS credential-store boundary backed by `keyring`;
- a default dependency that fails closed with
  `credential_store_unavailable`.

It deliberately does not contain provider network adapters, credential
persistence outside Windows Credential Manager or Linux Secret Service, a
plaintext fallback, a database, an Agent runtime, or an application CLI. The
credential-store boundary is not wired into provider routes yet. Those routes
become operational only when provider validation and connection orchestration
are supplied to the app factory.

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
