# Agents workspace scope isolation

## Changes

- Partition the workspace API's mixed local/global result by scope and workspace ID before rendering editable rows, counts, pagination, or collecting batch IDs.
- Render inherited global Agents read-only from the same catalog revision. Remove the redundant global request and frontend name-based shadow resolution; preserve backend reasons and shadow IDs, including Unicode matching decisions.
- Derive the no-fallback warning from the backend shadow relation.

## Verification

- Reproduced the mixed-response regression before the fix.
- AgentsSettings component tests: 8 passed, including global-only inheritance, mixed scope batch isolation, and Unicode shadow decisions across cursor pages.
- TypeScript check and production build passed; the existing large-chunk warning remains.
- Full frontend suite: 47 files, 403 tests passed. Git diff whitespace check passed; SymbolLattice reported an up-to-date source index after the fix.
- No backend/API contract changes. No installed-runtime/browser verification or local installation performed in this slice.
- Version remains 0.20.3; no commit or push requested.
