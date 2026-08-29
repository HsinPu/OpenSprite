# 0078 — Basic Context recovery

## Objective

Keep the existing single-summary Context manager simple while correcting stale
OpenRouter capabilities and one recoverable Provider context-limit failure.

## Changes

- Refreshed the OpenRouter model catalog once when a still-fresh cache misses a
  selected model, without adding connection callbacks or persistent cache.
- Recognized bounded, explicit Provider context-limit error responses while
  keeping unrelated and oversized upstream errors sanitized.
- Allowed one first-round retry only after no text or tool call was emitted;
  the retry compacts one eligible older block and never deletes raw Messages.
- Reused the existing `run.started` event as the visible Context-preparation
  step instead of adding a new event type or database migration.
- Added safe lifecycle logs containing identifiers, limits and usage only.

## Public impact

The HTTP and SSE schemas are unchanged. A first Provider context rejection may
now produce one additional model request after one bounded compaction. Existing
Run error codes and persisted conversation formats remain unchanged.

## Verification

- Backend: `431 passed, 2 skipped` with warnings treated as errors.
- Frontend: `143 passed`; TypeScript typecheck and production build passed.
- OpenRouter fresh-cache miss refresh and subsequent cache reuse.
- Bounded Provider context-error classification and oversized-body rejection.
- One safe pre-output compaction retry, a second-rejection stop and no retry
  after partial output.
- Python compileall, offline lock check and dependency check passed.
- Repository diff check passed without tracked generated artifacts.

## Remaining work

No Provider tokenizer, vector search, multi-level summary, background compaction
or new Context event type is included.
