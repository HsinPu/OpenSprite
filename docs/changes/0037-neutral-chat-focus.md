# 0037 — Neutral chat focus treatment

## Objective

Remove the distracting orange frame shown whenever the message textarea is
focused while preserving a clear keyboard focus indicator.

## Change

- Changed the shared ChatWorkspace focus-visible outline from the orange brand
  color to the existing neutral muted token.
- Reduced the outline from 3px with a 2px offset to a quieter 2px with a 1px
  offset, keeping the textarea, buttons, and execution record keyboard-visible.
- Kept textarea borders and composer layout unchanged; only the focus treatment
  changed.

## Verification

- Browser computed style confirms the focused textarea no longer uses the orange
  outline and retains a neutral focus outline.
- Frontend component tests, TypeScript checking, production build, and
  `git diff --check` are required before commit.
