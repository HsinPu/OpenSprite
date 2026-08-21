# 0027 - Future model preference indicators

## Summary

Changed two unimplemented model preferences from misleading demo switches into
explicit non-interactive future-feature rows.

## Changes

- Marked automatic model selection and model-name display as 「未來上線」.
- Removed their unused values from `DemoSettings`.
- Replaced interactive checkboxes with accessible informational rows.
- Kept current model fallback and display behavior unchanged.

## Verification

- Settings page component tests prove both labels and badges are present and no
  checkbox is exposed.
- Full frontend tests, TypeScript and production build run before commit.
