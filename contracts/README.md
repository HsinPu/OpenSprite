# Contracts

`provider-connections.openapi.json` is the authoritative consumer-visible HTTP
contract for the local provider-connection boundary. The frontend and backend
must derive their request, response, and error expectations from this file; they
must not maintain incompatible copies.

The contract currently covers:

- backend liveness at `GET /healthz`;
- the fixed `openai`, `anthropic`, and `openrouter` provider catalog;
- validate-then-save connection replacement;
- testing and deleting a stored provider connection;
- stable public summaries and a secret-safe error envelope.

This first contract has no pagination, filtering, sorting, event, webhook, or
WebSocket surface. Any future contract must be added explicitly and follow the
evolution rules recorded in `docs/architecture/overview.md`.
