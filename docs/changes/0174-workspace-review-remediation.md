# Workspace release review remediation

## Objective

Resolve the four confirmed findings from the 0.12.0 Managed Workspace release
review without changing the published API shape or moving user files.

## Changes

- Reserved the fixed Default Workspace name and directory during v1 catalog
  migration, generated deterministic collision fallbacks, and validated the
  complete v2 document before atomic replacement.
- Rejected mount roots that are parents of the user home, `.opensprite`, or the
  OpenSprite installation tree.
- Rejected Unicode control and formatting characters in Workspace names,
  managed directory names and mount aliases.
- Added a localized confirmation before changing an existing mount path or
  raising its authority from read-only to read-write.

## Verification

- Regression tests first reproduced all four findings.
- Backend pytest: `707 passed, 2 skipped`; the focused Workspace suite passed
  `39` tests.
- Frontend Vitest: `279 passed`; Workspace/i18n passed `17` focused tests.
- TypeScript typecheck, production build, Python compileall, uv lock and
  dependency checks passed.
- A 390px isolated browser run showed the confirmation before a path-changing
  PUT; cancelling retained the editor and produced no update request.
- Windows installer isolation passed.

## Remaining work

- No push or installed-computer update is included.
