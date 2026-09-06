# Release 0.13.0 — global and Workspace Skills

The package/lock version advances from 0.12.1 to 0.13.0. README, Skills,
Agent/Context, system-prompt and local-data-layout documentation describe lazy
instruction loading, explicit hash approval, Workspace overrides and archiving.
The Agent HTTP contract adds optional skillIds and strict Skill event payloads.

## Verification

- Backend: 750 passed, 3 existing skips, with warnings treated as errors.
- Final version/contract subset: 16 passed.
- Frontend: final full suite passed all 284 tests, including the browser Escape
  regression; the focused SkillsSettings suite has 3 passing tests.
- TypeScript and production build passed; existing bundle-size warning remains.
- compileall, uv lock --check --offline and uv pip check passed.
- Windows installer isolation passed with package 0.13.0. Windows retained some
  isolated native test binaries in installer quarantine; no user-data reset.
- Linux helper unit coverage is part of pytest; Git Bash syntax checks passed.
  Real Linux GUI/systemd execution remains unverified.
- In-app browser: isolated port 8766/temp root, global create/confirm and composer
  discovery; desktop and 390px Drawer checked. No horizontal page overflow at
  390px. Escape/focus regression found and fixed, then verified live (0183).
- SymbolLattice 0.511.0 matches guidance; repository index is initialized and
  reports stale=false. Unresolved graph edges are not asserted as evidence.
- git diff --check passed. Changes are split into reviewable commits.

## Remaining external validation

The controlled real-model positive/near-match/negative probe returned Provider
HTTP 401 in all cases. No model-quality success is claimed. Update credentials
through the normal user workflow and rerun the documented probe before relying
on automatic selection quality. No credentials were changed by this release.

No push or installed-application update was performed. Temporary browser service
was stopped and viewport override reset after verification.
