# 0015 — OpenRouter provider connection

## Objective

Add OpenRouter as the third fixed provider while preserving the existing secure
credential lifecycle and public connection contract.

## Changes

- Expanded the authoritative provider catalog to the fixed order OpenAI,
  Anthropic, OpenRouter across OpenAPI, backend models, state, and the strict
  frontend consumer.
- Added the fixed credential name `provider.openrouter.api-key` to the native
  keyring adapter; unsupported caller-provided provider names still fail closed.
- Added OpenRouter validation through `GET https://openrouter.ai/api/v1/key`
  with Bearer authorization only, a 30-second timeout, disabled redirects, a
  1 MiB response cap, and a required JSON `data` object.
- Added the OpenRouter settings card and `OR` badge with the same connect,
  manage, test, delete, focus, secret-clearing, and concurrency behavior as the
  existing providers.
- Kept provider metadata schema version 2; adding the third allowed provider is
  additive and does not scan or migrate another location.

## Public impact

`GET /api/providers` now returns exactly three summaries and `ProviderId` adds
`openrouter`. Existing routes, fields, statuses, error envelopes, Host/Origin
policy, and credential semantics are unchanged. Dynamic OpenRouter model
discovery is intentionally deferred to change 0016.

## Verification

- Authoritative OpenAPI JSON parse and contract checks: passed.
- Full backend suite with warnings as errors: 227 passed.
- Full frontend Vitest suite: 3 files, 35 tests passed.
- Frontend TypeScript check and production build: passed; the existing
  541.83 kB chunk advisory remains non-blocking.
- `git diff --check`: passed before independent review.

All provider tests use fake keyrings and mock HTTP transports. No real
credential was read or written and no live OpenRouter request was made.

## Remaining work

The OpenRouter model catalog remains empty in the frontend until the separately
reviewed dynamic-model contract and implementation are completed.
