# Release 0.14.0: Skill folder import

## Scope

Retain single SKILL.md import and add explicit folder selection, bounded
structure/YAML validation, preview and confirmed multipart import for global
and Workspace Skills. Preserve supporting files without granting execution or
reference-loading capability. Imported Skills remain disabled pending approval.
Version, OpenAPI, README and storage architecture are updated together.

The implementation follows bounded input validation and incremental verification:
browser validation is advisory, backend validation is authoritative, and disk
commit uses a recoverable journal with no existing-directory overwrite.

## Verification

- Backend: `uv run pytest -W error -p no:cacheprovider`: 782 passed, 3 skipped.
- Frontend: `npm test -- --run`: 304 passed across 41 files.
- Frontend typecheck and production build passed. The existing large-bundle
  warning remains; no bundle-size claim is made.
- Backend compileall, offline lock check and installed dependency check passed.
- Windows installer isolation suite passed; locked quarantine leftovers reported
  by the harness were preserved, not manually removed.
- Git Bash syntax checks passed for Linux install/uninstall/test scripts.
- `git diff --check` passed.
- SymbolLattice 0.511.0 matched repository guidance; status reported initialized
  and not stale after the source/test changes.

An isolated backend on port 8766 with separate test data served the production
build. The in-app browser selected a real two-file folder, displayed its name,
description, relative files and SKILL.md preview, then imported it only after
confirmation. The resulting Skill displayed pending approval. A 390px preview
was also exercised without observed horizontal overflow. Cancellation/focus and
failed-import retry behavior are covered by component tests. The isolated
backend was stopped; installed port 8765 and user data were not updated.

## Limits

Browser upload does not reliably expose source symlink identity or empty
directories. Only regular uploaded bytes are recreated at the validated
destination. Supporting scripts are stored but never run or placed in Context.
Real Linux GUI/systemd and separate Chrome/Edge verification were not performed.
No new model-routing claim is made; this change does not alter load_skill.
No push or installed-machine update was performed.
