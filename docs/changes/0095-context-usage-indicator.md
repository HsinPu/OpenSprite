# Context usage indicator

## Objective

Show the current model-request Context usage next to the composer model picker
without duplicating token counting in the browser.

## Changes

- Extract the latest extended `model.started` usage from the existing Run event
  stream and keep legacy events safe.
- Render `Context used / limit` beside the model selector, with a fallback limit
  from the selected model's effective Context budget.
- Mark warning and danger states from the backend-provided safe input budget and
  show a compacting status while the existing compaction event is active.
- Add responsive styling and Traditional Chinese, English and Japanese labels.
- Keep the indicator diagnostic only; it does not expose billing usage, prompt
  content, credentials or browser storage.

## Public impact

No new route, database table or event type is added. The existing SSE
`model.started` payload is consumed with optional Context fields; old persisted
events remain valid and display an unavailable numerator.

## Verification

- Component tests cover legacy extraction, fallback limits, compacting state and
  placement beside the model picker.
- Full frontend verification passed: 23 test files and 182 tests, TypeScript
  typecheck and production build.
- Browser checks at 1440px and 390px confirmed the indicator stays beside the
  model selector, remains visible on mobile and introduces no horizontal
  overflow.
- Backend contract and Agent Loop tests remain green from the preceding slice.

## Remaining work

Exact provider token accounting, billing display and historical Context charts
are intentionally outside this feature.
