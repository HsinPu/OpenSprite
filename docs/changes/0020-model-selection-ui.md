# 0020 Model selection UI

## Objective

Make the saved default model selection usable from both the settings dialog and
the chat workspace without adding a real chat-completion request.

## Changes

- Added a strict frontend client for `GET` and `PUT /api/settings/model`.
- Moved the confirmed selection to App-owned state so the settings dialog and
  chat selector cannot diverge.
- Added startup loading, static connected-provider choices, a safe no-selection
  state, and deterministic fallback to the first available OpenAI/Anthropic
  model when no saved selection exists.
- Added stale hydration protection so an older GET cannot overwrite a newer
  successful PUT, and kept failed saves on the last confirmed choice.
- Converted the chat model control from a disabled Demo button into an
  accessible grouped native selector. A stale or currently unavailable model is
  display-only, never presented as a selectable connected choice.
- Preserved the current dynamic OpenRouter behavior: discovery is in-memory,
  a temporary failure preserves an existing selection, and successful discovery
  can reconcile a model that no longer exists.

## Public impact

The browser UI now consumes the persisted model-selection API. It does not
write model selections, dynamic lists, or API keys to localStorage or the URL.
The chat transcript remains Demo data; selecting a model does not yet invoke a
provider completion API.

## Verification

- Frontend Vitest: 4 files, 56 tests passed.
- Frontend TypeScript check: passed.
- Frontend production build: passed; the existing Vite chunk-size advisory
  remains non-blocking.
- Manual local smoke: the current backend returned `200` from `/healthz` and
  `/api/settings/model`; the frontend showed the safe no-selection state and
  the AI-model settings dialog correctly rendered connected/disconnected
  provider state.
- `git diff --check` and CodeGraph status: passed before final repository
  review.

## Remaining work

- Chat messages remain the existing Demo flow; this slice does not call a
  selected model.
- General settings remain session-only.
- OpenAI and Anthropic retain the current fixed frontend catalogs. OpenRouter
  discovery remains on-demand and memory-only.
