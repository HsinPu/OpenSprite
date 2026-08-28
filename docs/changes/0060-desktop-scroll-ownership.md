# 0060 Restore desktop scroll ownership

## Objective

Prevent conversation content from expanding the whole desktop application
beyond the viewport and clipping the header or composer.

## Changes

- Gave the desktop App shell one definite `100dvh` height and a zero minimum
  height so its nested percentage heights resolve correctly.
- Made the desktop sidebar and content column inherit that definite height.
- Kept document scrolling disabled on desktop so the conversation and execution
  panes own their independent overflow.
- Restored automatic height, visible shell overflow and document scrolling below
  the existing 900px mobile-navigation breakpoint.

## Public impact

HTTP contracts, persisted state, conversation content and component behavior
are unchanged. Desktop keeps the header and composer inside the viewport while
long conversations scroll internally; mobile remains one naturally scrolling
document.

## Verification

- Live browser measurement at the user's 1341x1022 CSS viewport.
- Explicit desktop and mobile viewport checks with zero horizontal overflow.
- Complete frontend tests, TypeScript typecheck and production build.
