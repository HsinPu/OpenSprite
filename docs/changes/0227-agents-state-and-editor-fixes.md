# Agents state and editor fixes — 0.20.2

## Changes

- Fetch final child summaries when a parent becomes terminal, including when a prior request is still pending. Preserve run-generation guards.
- Refresh an expanded pending child result when its terminal summary arrives; also handle pending result responses arriving after that summary.
- Agent detail now returns nullable `developerInstructions` parsed by the existing backend TOML parser. The editor uses that field rather than regex parsing. Import still previews and submits the original file unchanged.
- Update the strict API adapter, OpenAPI schema, browser fixture, product version, and version assertions. No data migration or dependency changes.

## Verification

- Regression tests first reproduced the missing final refresh, stale empty result, and absent parsed detail field.
- Targeted service/routes tests passed (39); frontend editor and state tests verify user-visible transitions and preserved instruction meaning.
- Full frontend Vitest: 399 passed across 47 files; typecheck and production build passed (existing chunk-size and jsdom pseudo-element warnings remain).
- Backend service/routes and app/version contracts: 74 passed with warnings-as-errors and the cache plugin disabled because the existing cache directory is not writable.
- Compileall, offline uv lock check, uv pip check, and git diff --check passed. No dependencies added.

## Boundaries

- No commit, push, or installed-runtime update requested for this slice.
- No real-provider, Linux GUI/systemd, or live-browser verification claimed.
