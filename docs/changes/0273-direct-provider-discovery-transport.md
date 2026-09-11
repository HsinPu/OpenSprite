# Direct-provider discovery transport

## Implemented boundary

Adds OpenAI and Anthropic discovery to the existing provider validator and
credential orchestration service. Discovery is read-only and serialized with
credential changes by the existing per-provider lock.

- OpenAI uses GET /v1/models; candidate filtering excludes known non-text families.
  Name filtering is not proof of Responses API compatibility.
- Anthropic follows has_more/last_id using after_id. Repeated/invalid cursors fail
  without publishing a partial list.
- The complete operation has a 30-second deadline and a 4 MiB aggregate response
  bound. Redirects are not followed; error bodies are never surfaced.
- Known capabilities remain unchanged. New IDs use 8192/2048 and do not assume
  tool support.
- No credentials, settings, or model capacity records are changed.

## Sources

- https://platform.openai.com/docs/api-reference/models/object
- https://platform.claude.com/docs/en/api/models/list

## Integration status

This slice does not yet expose an HTTP route or replace the frontend fixed lists.
Shared model persistence/editing and runtime capability resolution must be wired
before enabling the new discovery controls.

## Verification

Offline httpx transport tests cover filtering, defaults, pagination, deduplication,
error sanitization, redirect refusal, looping cursors, and aggregate response size.
Service tests cover both providers with valid, rejected, missing, and incoherent
credentials without credential mutation. No live provider requests were made.

`uv run pytest -q -p no:cacheprovider tests/test_direct_models.py
tests/test_provider_connection_service.py tests/test_provider_adapters.py -W error`:
110 passed. Cache provider disabled because the existing pytest cache is not
writable in this execution environment; no permissions or old cache were changed.
