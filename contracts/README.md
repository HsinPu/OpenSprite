# Contracts

`provider-connections.openapi.json` is the authoritative consumer-visible HTTP
contract for the local provider-connection boundary. The frontend and backend
must derive their request, response, and error expectations from this file; they
must not maintain incompatible copies.

`ai-settings.openapi.json` is the authoritative consumer-visible HTTP contract
for the atomic model selection and response mode setting. It is separate from
provider credential lifecycle because it never returns or persists a raw API
key, dynamic model list, display label, or inference result.

The contract currently covers:

- backend liveness at `GET /healthz`;
- the fixed `openai`, `anthropic`, and `openrouter` provider catalog;
- validate-then-save connection replacement;
- testing and deleting a stored provider connection;
- on-demand discovery of connected OpenRouter text models;
- stable public summaries and a secret-safe error envelope.

The AI settings contract covers:

- reading the confirmed model selection and response mode;
- atomically saving both values for a connected Provider;
- clearing the model while preserving a selected response mode.

This first contract has no pagination, filtering, sorting, event, webhook, or
WebSocket surface. Any future contract must be added explicitly and follow the
evolution rules recorded in `docs/architecture/overview.md`.
