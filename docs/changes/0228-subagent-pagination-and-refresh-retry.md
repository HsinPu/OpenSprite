# Subagent pagination and refresh retry — 0.20.3

- Concatenate result pages verbatim, without inserting a newline at the 4,000-character page boundary.
- Keep existing cards visible after summary refresh failure and provide a retry button, including after the parent stops polling. Disable retry while loading.
- Add regressions for exact page concatenation and recovery after a failed terminal refresh. Both tests failed before the fixes.
- Update authoritative product version, lock metadata, contract versions, and version assertions to 0.20.3.
- No dependencies, data migrations, commit, push, or installed-runtime changes.

## Verification

- Subagent component tests: 10 passed; both new tests failed before implementation.
- TypeScript and production build passed; existing bundle-size warning remains.
- Backend app/version contracts: 35 passed. Offline lock and dependency checks passed.
- Git diff check passed; SymbolLattice reports an up-to-date index.
- No full-suite rerun, live browser, installer, or real-model verification for this focused slice.
