# Contracts

`provider-connections.openapi.json` is the authoritative consumer-visible HTTP
contract for the local provider-connection boundary. The frontend and backend
must derive their request, response, and error expectations from this file; they
must not maintain incompatible copies.

`ai-settings.openapi.json` is the authoritative consumer-visible HTTP contract
for the atomic model selection and response mode setting. It is separate from
provider credential lifecycle because it never returns or persists a raw API
key, dynamic model list, display label, or inference result.

`agent-chat.openapi.json` is the authoritative consumer-visible HTTP and SSE
contract for durable conversations, one-message agent runs, safe semantic Run
events, and cancellation. It deliberately excludes raw Provider payloads,
credentials, internal prompts, hidden reasoning, and unapproved tool surfaces.

`general-settings.openapi.json` is the authoritative HTTP contract for the
persisted interface locale and time-zone choice. It remains separate from AI
model configuration.

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

The general settings contract covers:

- reading the confirmed interface locale and time-zone choice;
- atomically replacing both values from fixed supported catalogs.

The agent chat contract covers:

- listing conversations and their visible persisted messages;
- atomically accepting one user message and one idempotent Run;
- reading a Run snapshot and replaying/following semantic events over SSE;
- cancelling one active Run without fabricating a successful answer.

Provider connections and AI settings have no event, webhook, or WebSocket
surface. Agent chat has bounded cursor pagination and one server-to-browser SSE
surface, but no webhook or WebSocket contract. Any future contract must be added
explicitly and follow the evolution rules recorded in
`docs/architecture/overview.md`.
