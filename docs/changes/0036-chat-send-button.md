# 0036 — Chat send-button clarity

## Objective

Make the primary chat action visible, optically centered, and consistent across
its idle, ready, running, and cancelling states.

## Root cause

The generic `.chat-workspace button { color: inherit; }` selector had greater
specificity than the send-button rule. The arrow inherited the same dark color
as its dark background, so the control appeared as an empty block. The button
also relied on a font glyph and had no explicit centering layout.

## Change

- Replaced font glyphs with decorative SVG send and stop icons.
- Fixed both controls at 48 by 48 pixels with grid centering.
- Added explicit high-contrast ready, disabled, stop, and cancelling colors
  using the existing chat tokens where applicable.
- Preserved the existing accessible names, submit behavior, cancellation
  behavior, focus treatment, and touch target.

## Verification

- Component tests verify both controls render stable SVG icons and that send is
  disabled until non-empty text is entered.
- Frontend tests, TypeScript checking, production build, and live browser visual
  inspection are required before commit.
