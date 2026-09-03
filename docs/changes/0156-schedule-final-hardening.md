# Schedule final hardening

## Objective

Close public error and state-transition gaps found during final schedule review.

## Changes

- Added `scheduled_tool_approval_required` to the public Run error contract so a
  failed scheduled Run remains readable instead of becoming a serialization 500.
- Added matching safe frontend error handling in all supported locales.
- Editing a paused schedule now preserves its paused state and null next-run
  time; pause and resume reject invalid source states.
- Added a regression proving scheduled Runs use their fixed execution profile
  and never enable full Prompt logging.

## Verification

Focused Agent loop, chat service, schedule coordinator, repository, and route
tests pass with the new public error and transition behavior.
