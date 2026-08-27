# Agent chat application boundary

## Objective

Separate Agent chat use-case orchestration from the consumer-facing HTTP API
package without changing runtime or contract behavior.

## Changes

- Moved `AgentChatService`, its protocol, errors and fail-closed implementation
  from `api/chat_service.py` to `application/chat_service.py`.
- Restricted `api/` to routes, public models and SSE serialization.
- Updated system composition, HTTP callers and tests to use the new application
  boundary without a compatibility import alias.
- Added an AST architecture guard preventing the application layer from
  importing HTTP frameworks, API modules, runtime composition or the concrete
  SQLite adapter.
- Updated the Agent chat dependency diagram and responsibility descriptions.

## Public impact

None. HTTP/SSE operations, payloads, error mappings, persistence schemas and
runtime behavior are unchanged. The internal Python import path is intentionally
changed under the new-install-only policy.

## Verification

- `uv run pytest -W error -p no:cacheprovider tests/test_agent_architecture.py tests/test_agent_chat_service.py tests/test_agent_chat_app.py tests/test_runtime.py`
- `uv run python -m compileall -q src tests`
- Search confirmed `opensprite_backend.api.chat_service` and the removed source
  path have no remaining references.
- `git diff --check`

## Remaining work

- Split oversized frontend application and settings responsibilities.
- Add the approved frontend internationalization boundary.
