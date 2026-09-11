# Agents settings layout and discovery

## Scope

Align the Agents settings page with the Skills settings layout while preserving Agent editing, TOML import preview, model selection, backend APIs, inheritance, permissions, and execution behavior.

## Implementation

- Search the complete loaded scope by NFC-normalized, case-insensitive name before UI pagination. Share search and status filters with inherited globals; retain separate counts and pages.
- Filter enabled/disabled by the individual setting. Issue filtering excludes effective, disabled, master-disabled and workspace-shadowed reasons. It reflects the reason supplied by the existing API without changing backend precedence.
- Reset both pages when filters change, clamp pages to result counts, and keep the fixed 20-item page size.
- Simplify the heading and rows, collapse explanatory copy, show a paused notice, and keep edit/remove icons. Normal effective rows no longer repeat a status tag.
- Keep inherited entries read-only, with a section-level label and global-management link. Preserve no-fallback and workspace-removal warnings.
- Keep batches scoped to all owned entries, not search results or inherited globals. Add an explicit unfiltered-scope confirmation and restore focus to the actual batch trigger.
- Preserve visible data after reload failure and block writes until a successful retry. Preserve the existing committed-editor protection against duplicate submission.
- Add localized search/clear/filter/result/error messages in Traditional Chinese, English and Japanese, plus responsive filter and row layout.

## Verification

- Full frontend suite: 55 files and 467 tests passed after correcting an icon import in the first verification run.
- Two additional regression tests were subsequently added for pagination reset/initial failure and workspace-removal/batch-focus behavior; the final Agents suite passed all 21 tests.
- Typecheck, production build and `git diff --check` passed. Existing JSDOM pseudo-element and Vite bundle-size warnings remain.
- Desktop browser preview at localhost:5174 (1001px viewport): search clear, workspace inheritance section, create dialog and cancel/focus return passed. Page and dialog had no horizontal overflow.
- Real local Agent catalog was empty. Populated lists, Unicode search across cursor pages, filters, batch scope and reload failure were verified using component test fixtures; no live Agent definitions or settings were written.
- Exact mobile viewport and 200% zoom remain unverified; no claim of complete responsive-browser coverage.
- No version bump, commit, push or local installation in this slice.
