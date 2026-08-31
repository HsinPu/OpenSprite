# Output continuation selector

## Objective

Expose the Run-snapshotted output-continuation policy as a complete settings
choice instead of the temporary on/off switch.

## Changes

- Replace the AI settings switch with an Ant Design selector for off, 1, 2, 3,
  5, or unlimited continuation attempts.
- Show a policy-specific explanation and disable the selector while settings
  are being saved.
- Add Traditional Chinese, English, and Japanese labels and descriptions.
- Render unlimited continuation events as `attempt/∞` while preserving numeric
  historical events.
- Update browser-contract and component tests for the selector and nullable
  event maximum.

## Safety

`Unlimited` affects the Run policy only. The backend still enforces the
64-attempt hard cap plus cancellation, Context, assistant-size and Provider
failure boundaries.

## Verification

- Settings selector component test.
- SSE parser and execution-record tests for nullable `maxAttempts`.
- Full frontend test, typecheck, and production build.
