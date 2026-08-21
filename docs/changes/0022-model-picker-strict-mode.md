# 0022 Model picker StrictMode recovery

## Objective

Allow OpenRouter model discovery to complete in the React development runtime
and use direct model-selection wording in the settings interface.

## Changes

- Reset the mounted-state guard whenever the model settings component mounts,
  including React StrictMode's development remount simulation.
- Continue rejecting stale responses after a real unmount while accepting the
  current model response after the simulated remount.
- Renamed the visible field from `預設模型` to `模型`, its placeholder to
  `選擇模型`, and the settings introduction to describe the selected model
  without calling it a default model.

## Verification

- Added a StrictMode regression test that proves the returned OpenRouter model
  list unlocks the model selector.
- Updated the existing settings interaction tests to use the new field label.
- Frontend unit tests, TypeScript, production build, and browser verification
  are recorded with the implementation commit.
