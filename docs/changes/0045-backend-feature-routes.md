# 0045 Backend feature routes

## Objective

Keep the FastAPI application factory focused on composition by moving Provider and AI-settings HTTP routes to their owning API modules.

## Changes

- Added `api/provider_routes.py` for Provider paths, dependency lookup, public error serialization and OpenAPI response metadata.
- Added `api/ai_settings_routes.py` for AI-settings paths, dependency lookup, public error serialization and OpenAPI response metadata.
- Reduced `app.py` to application state binding, local-security middleware, exception handlers, health and router composition.
- Added an architecture guard that rejects future `/api/` route declarations inside `app.py`.

## Public impact

None. Paths, methods, operation IDs, payloads, status codes, error envelopes, local security and dependency behavior are unchanged.

## Verification

- Targeted Provider, AI-settings, Agent Chat, OpenAPI contract and architecture tests: 107 passed.
- Backend source and tests compiled successfully.

## Remaining work

- Provider connection domain composition remains in `provider_connections.py`; it should only be split when a new approved capability creates an independent responsibility.
