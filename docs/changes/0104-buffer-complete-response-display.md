# Buffered complete response display

## Objective

Allow the browser to render a model response either incrementally or as one
assembled answer while retaining the existing streamed execution pipeline.

## Changes

- Capture `responseDelivery` when a Run is watched so a setting change does not
  alter an active response halfway through.
- Keep `stream` behavior unchanged and append each `assistant.delta` directly
  to the visible response.
- In `complete` mode, buffer deltas and reveal the assembled text at terminal
  events; preserve partial text for provider errors, cancellation, interruption
  and SSE failures.
- Keep Provider requests, SSE, execution records, Context, continuation and
  Prompt logging unchanged.

## Verification

- Hook tests cover streaming parity, complete-mode terminal reveal, and error
  partial-text preservation.
- Existing ChatWorkspace tests and TypeScript typecheck pass.
