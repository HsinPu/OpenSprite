# Skills review remediation

## Scope

- Preserve Skill catalog entries created before portable UTF-8 directory limits were introduced while keeping the stricter rule for new Skills and folder imports.
- Prevent workspace-scoped Skill controls from displaying data owned by the previously selected Workspace.
- Fail closed on malformed Skills API success and error responses.
- Render a localized fallback when a failed model-selected Skill has no metadata.

## Verification

- `uv run pytest -W error -p no:cacheprovider`: 792 passed, 3 skipped.
- `npm test -- --run`: 319 passed.
- `npm run typecheck` and `npm run build` passed; Vite reported only the existing large-chunk advisory.
- `python -m compileall -q src tests`, `uv lock --check --offline`, and `uv pip check` passed.
- `git diff --check` passed.
- `SymbolLattice status . --json` reported a fresh index with no stale reasons.
