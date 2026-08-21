# 0016 OpenRouter dynamic models

## Scope

- Add bodyless `POST /api/providers/openrouter/models` to the authoritative
  provider OpenAPI contract.
- Discover the connected account's models from OpenRouter
  `/api/v1/models/user` with the stored Bearer credential.
- Return only valid text-input/text-output model ids and names, deduplicated,
  stably sorted, bounded to 1000 items and a 4 MiB upstream response.
- Add session-memory loading, retry, searchable selection, stale-response
  protection, and disconnect fallback to the settings UI.
- Keep the API key, upstream response, and dynamic model catalog out of browser
  storage, URLs, logs, Provider metadata, and every `.opensprite` path.

## Verification

- Backend: 255 tests passed with warnings treated as errors.
- Backend bytecode compilation passed.
- Frontend: 45 Vitest tests passed, including mixed-provider fallback,
  stale-response invalidation, searchable name/full-id filtering, and Unicode
  code-point boundaries.
- Frontend TypeScript checking and production build passed. The build retains
  the existing advisory for a JavaScript chunk larger than 500 kB.
- Offline lock checking and the installed-package compatibility check passed.
- Browser inspection confirmed the third OpenRouter card at desktop and mobile
  layout widths with no horizontal overflow or console warning/error. Dynamic
  connected-model behavior remained mock-tested because no real key was used.
- `git diff --check` passed.
- Tests use mock HTTP transports and fake credential/state repositories; no
  real OpenRouter credential, operating-system keyring, or external request was
  used.
