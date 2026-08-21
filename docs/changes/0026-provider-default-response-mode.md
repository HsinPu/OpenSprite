# 0026 - Provider-default response mode

## Summary

Added a fourth response mode that delegates reasoning-strength selection to the
model Provider by omitting that parameter from future inference requests.

## Changes

- Added the persisted `default` response mode to the backend, contract and
  strict frontend parser.
- Made `default` the side-effect-free value returned when no settings file
  exists; existing saved modes remain unchanged.
- Added the visible 「預設」 choice before 快速、平衡 and 深入.
- Expanded the segmented control to four equal columns.
- Recorded that `default` must mean parameter omission when the inference layer
  is implemented; this slice does not add a chat runtime.

## Verification

- Backend AI settings and contract tests.
- Frontend AI settings, settings page and App tests.
- Full backend and frontend verification before commit.
