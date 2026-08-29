# 0069 Configurable chat auto-scroll

## Objective

Follow newly sent and streamed chat content without pulling a user away from
older Messages, and let the behavior be disabled through persisted settings.

## Changes

- Added an Ant Design Switch under General / Startup and conversations for the
  confirmed `autoScroll` value.
- Added a focused conversation-viewport hook that positions an opened
  Conversation at its latest content, follows explicit sends, coalesces stream
  growth through `requestAnimationFrame` and pauses when the user moves more
  than 96 pixels from the bottom.
- Restored follow when the user returns near the bottom. Disabling the setting
  cancels pending follow work and prevents send or stream updates from moving
  the viewport.
- Wrapped older-Message loading with height-delta compensation so prepending
  content preserves the visible reading position regardless of the setting.
- Kept Agent Run, event SSE, historical execution navigation, backend chat,
  database and browser storage unchanged.
- Added Traditional Chinese, English and Japanese setting copy.

## Verification

- Focused Switch, ChatWorkspace wiring and auto-scroll lifecycle tests passed.
- Full frontend verification passed: 15 test files and 128 tests, TypeScript
  typecheck and the Vite production build.
- The live browser positioned an opened Conversation at the bottom, persisted
  the Switch off across reload, restored it to `true`, and showed the complete
  control at the narrow viewport without horizontal overflow or console errors.
- No model message was sent during browser verification.
