# 0012 - Frontend provider connections

## Objective

Replace the AI-model settings demo connection state with the approved local
Provider Connections HTTP consumer, while retaining the existing white settings
dialog, model catalog, and session-only general preferences.

## Changes

- Added a small typed `/api/providers` client that accepts only the fixed
  OpenAI/Anthropic catalog, order, fields, status values, and UTC timestamps
  defined by `contracts/provider-connections.openapi.json`. GET, PUT, and POST
  require their exact `200` success status; malformed or unexpected successful
  payloads fail closed and no response body, server message, or raw key is
  rendered or logged.
- The models page loads the catalog on mount and provides loading, retry, safe
  error, status, replace, test, and idempotent delete states. Operations are
  tracked independently per provider with generation guards: repeated actions
  for one provider cannot overlap, different providers remain independent, and
  a failed-test refresh merges only its own persisted summary.
- API keys exist only in an Ant Design password modal owned by the settings
  dialog's subtree. They are never stored, prefilled, or shown; the modal is
  unmounted after success or cancellation and clears its local value on success,
  error, cancel, and unmount. Its submission and Escape/close paths are guarded
  while a PUT is active.
- A connect failure is announced only by the modal field error; its temporary
  background provider-progress message is removed so assistive technology does
  not receive a duplicate failure announcement.
- The settings dialog restores focus to the element that opened it (or the
  settings button if that opener is gone). Provider cards expose busy state and
  model selectors share stable helper text through `aria-describedby`.
- Local model options are keyed by provider id. Only stored connections expose
  models, and a disconnected selected provider falls back to the first remaining
  local model when one exists.
- Added same-origin `/api` dev and preview proxying to `127.0.0.1:8765` with
  `changeOrigin: false`, plus focused Vitest/jsdom/Testing Library coverage.

## Public impact

The frontend now consumes the existing provider contract; no contract, backend,
route, CORS, credential-store, or installer behavior changed. The model catalog
is intentionally still local static data and no provider model-list request is
made.

## Verification

On Windows in this repository:

- `npm ci --ignore-scripts` passed (170 packages, 0 vulnerabilities);
- `npm run typecheck` passed;
- `npm test` passed (3 files, 34 tests);
- `npm run build` passed; it emitted Vite's existing >500 kB chunk advisory; and
- `git diff --check` passed.

The focused suite covers request shape, disconnected/connected coherence,
impossible UTC dates, exact GET/PUT/POST success statuses, strict error
envelopes and status-code matching, DELETE invalid bodies, safe errors and
retry, per-provider deferred overlap and
stale-refresh protection, password-modal portal/keyboard/duplicate-submit and
secret cleanup, focus restoration at desktop and 390px, test-then-refresh, and
provider-filtered model options. Browser visual validation is not included
because no browser process was launched.

## Remaining work

- Model catalog retrieval is out of scope until a distinct provider-model
  contract exists.
- The existing Vite production bundle remains above its 500 kB advisory limit;
  this slice does not restructure unrelated application chunks.
