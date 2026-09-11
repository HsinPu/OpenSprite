# Model refresh selection safety

## Scope

First slice of unified provider model discovery. Existing default capacities and
provider credentials are unchanged.

- Keep the previously loaded OpenRouter choices while refreshing and on errors.
- Explicit invalidation still clears the cache, and stale requests cannot restore it.
- Do not silently replace a persisted OpenRouter selection when discovery no longer
  returns that model. The user must choose another model explicitly.

## Verification

- Hook regression coverage for pending/failed refresh and stale invalidated responses.
- Settings regression coverage retains a missing selection after a successful retry.
- `npm test -- --run tests/useProviderCatalog.test.tsx tests/SettingsPage.test.tsx`: 38 passed.
- `npm run typecheck`: passed.
- `git diff --check`: passed (line-ending warnings only).
- No live provider requests or installed-runtime deployment performed.

## Remaining scope

OpenAI/Anthropic discovery, shared refresh controls for custom providers, and built-in
model capability management are not implemented by this slice.
