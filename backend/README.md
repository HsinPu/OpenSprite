# Backend

This directory contains the minimal Python 3.12+ FastAPI foundation for the
local OpenSprite service. `contracts/provider-connections.openapi.json` is the
authoritative HTTP contract.

The current slice provides:

- a typed ASGI `create_app()` factory;
- `GET /healthz`;
- thin provider-connection routes and public models;
- an explicit `ProviderConnections` dependency seam;
- a default dependency that fails closed with
  `credential_store_unavailable`.

It deliberately does not contain provider network adapters, credential
persistence, a plaintext fallback, a database, an Agent runtime, or an
application CLI. Provider routes become operational only when a secure
operating-system credential implementation and provider validators are supplied
to the app factory.

After dependency synchronization, run the focused checks from this directory:

```powershell
uv sync --dev
uv run pytest
```
