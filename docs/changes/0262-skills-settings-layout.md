# Skills settings layout and discovery

## Scope

Improve the existing Skills settings surface without changing backend APIs, inheritance, model loading, permissions, import formats, or filesystem removal semantics.

## Implementation

- Search the complete already-loaded scope collection by NFC-normalized, case-insensitive name before pagination. Share the search and status filter with the read-only inherited collection.
- Keep enabled/disabled filters based on the individual enabled setting, not effective state. The issue filter uses file/catalog state, not master-disable or workspace shadowing.
- Reset pages on filter changes and clamp them after item counts change. Keep batch counts and operations tied to the complete unfiltered scope.
- Simplify the introduction, collapse usage details, show a paused notice, replace large empty states with contextual text, and show result totals.
- Keep name, switch and remove icon rows without descriptions. Inherited rows have no mutation controls; show exceptional states only, plus a link to manage global Skills.
- Preserve loaded rows after reload failure while disabling mutations until a successful refresh. Scope/workspace switches still clear previous rows and invalidate pending requests.
- Add three-language messages, wrapped long names, responsive filters, and a single focus treatment for the search input.

## Verification

- Focused SkillsSettings suite: 27 tests passed, including 297-item search, Unicode/case normalization, full-scope batches, enabled versus effective state, and stale-write protection.
- Full frontend suite: 55 files and 459 tests passed; typecheck and production build passed. Existing JSDOM pseudo-element and large-bundle warnings remain.
- Browser preview with real data: `wordpress` matches 2 of 297 global entries and the same 2 inherited entries. Workspace-owned entries remain empty and inherited entries remain read-only.
- Desktop browser verified; exact mobile viewport and 200% zoom checks remain unverified.
- No live Skill settings were changed in browser verification. No version bump, local install, commit or push requested.
