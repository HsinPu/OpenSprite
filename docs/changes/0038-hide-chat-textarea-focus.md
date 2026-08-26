# 0038 — Hide chat textarea focus frame

## Objective

Hide the focus frame around the message textarea when the user clicks into it,
as requested, without changing the composer border or send-button states.

## Change

- Removed the textarea from the shared orange/neutral focus-outline selector.
- Explicitly set the textarea focus-visible outline to `none`.
- Kept neutral focus visibility for chat buttons and execution-record summaries;
  only the textarea frame is hidden.

## Verification

- Browser computed style confirms the focused textarea has no outline, border, or
  box shadow while the surrounding composer remains unchanged.
- Frontend component tests, TypeScript checking, production build, and
  `git diff --check` are required before commit.
