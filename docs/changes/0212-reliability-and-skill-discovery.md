# 0.19.0 reliability and discovery work plan

Status: implementation and automated verification complete; runtime limits below.

## Approved slices

1. Chat submission: pending guard, preserve unaccepted draft, stable request ID on retry.
2. Accepted Run recovery: retain accepted identity and retry read/stream recovery without posting another Run.
3. Skills: bounded on-demand model discovery, efficient scan lookup and management list rendering. Preserve scope/enable/shadowing policy and immutable snapshots; no installation count limit.
4. Settings: lazy-loaded boundary with loading and recoverable failure UI.
5. Backend: separate schema/migration ownership and bounded Agent phases, preserving transaction/lock and task ownership.
6. Version 0.19.0, documentation and full validation.

No automatic installation or push. Existing 0.18.2 changes remain in the working tree.

## Verification

Deferred requests, duplicate submit, lost response, retry identity, edited drafts, accepted-read recovery; Skills discovery and isolation/context bounds; settings chunk/error/state behavior; backend parity and full checks.

## Checkpoint 1

Implemented synchronous in-flight submission guard and stable request payload for same-message retry. Composer clears only an accepted, unchanged draft. Initial focused hook/component checks passed; accepted-Run recovery and all subsequent slices remain pending. Product version has not yet been changed.

## Checkpoint 2

Accepted Run identity now survives hydration failures. Read/stream recovery uses that identity without another POST; pending accepted Runs block another submission. Automatic recovery is bounded and does not retry terminal Run errors. Focused chat checks: 36 tests passed, TypeScript passed.

Settings now imports its page on first open, retaining the mounted page after close and providing localized loading/error/retry/close UI. App tests are being adapted to the asynchronous boundary; full validation remains pending. Skills discovery, backend separation, version bump and final checks are still outstanding. This is not a release/completion receipt.

## Checkpoint 3

App async-boundary tests pass (28). Skills now offers `discover_skills` with 20-item pages and explicit truncated-description indicators, searching only the accepted effective snapshot. The initial prompt includes a count instead of all descriptions; `load_skill` keeps the full-instruction boundary. Discovery responses are checked against Context budget. Scan duplicate detection now uses sets. New deterministic discovery-to-load integration and complete-pagination tests added; broader validation, management rendering efficiency, backend extraction and release work remain pending.

## Checkpoint 4

Extracted SQLite DDL and ordered migration code into `conversations/sqlite_schema.py`. Repository still owns connection lifetime, permissions, locking and runtime transactions; migration statements and commit/rollback behavior were moved unchanged. Repository baseline: 31 passed before extraction. Repository, Workspace and Skill integration checks: 92 passed after extraction, with pytest cache disabled because the existing cache directory is not writable. Agent phase extraction, management rendering, broader checks and version/docs remain outstanding.

## Checkpoint 5

Skills management renders at most 20 rows per own/inherited list, with independent pagination. Scope changes reset pages and list shrink clamps the current page. Batch operations continue using the complete scope and catalog revision, not the displayed subset. Frontend typecheck and 24 SkillsSettings tests passed, including a 45-item pagination and batch-scope regression. Network list pagination is not claimed: this slice bounds DOM work while retaining the current complete catalog response.

## Checkpoint 6

Extracted the internal Skill call phase into `agent/skill_phase.py`, preserving event persistence and Context checks without creating tasks or owning connections. Agent/Skill focused tests: 46 passed. Full frontend: 43 files, 355 tests passed. Full backend verification started; completion evidence pending. Product version remains unchanged until that run finishes; release documentation and remaining verification still required.

## Checkpoint 7

Full backend: 850 passed, 3 skipped. Frontend typecheck/build passed; output includes a separate SettingsPage chunk (382.55 kB) and initial JS (1,063.28 kB); the remaining large-chunk warning is not suppressed. Updated product version to 0.19.0 after the full run; version/contract checks (35 tests), compileall, offline lock check and dependency compatibility passed afterward. Architecture docs updated. Installer isolation, browser checks, final diff/freshness and completion audit remain pending; no installation or push performed.

## Checkpoint 8

Windows installer isolation passed with version 0.19.0. Windows retained isolated native test binaries; the test quarantined them under its temporary directory and warned, without touching the installed application. Git diff check passed; SymbolLattice reports fresh generation a5b032d1-0db4-4e1c-a8a3-92d197eaff26 before this documentation update. Browser verification and the final completion audit remain pending.

## Final verification and limits

- Chat submission/recovery: focused 36 tests; full frontend 355 tests passed.
- Skills: deterministic discovery/load integration, complete 57-item pagination,
  snapshot policy and existing integration tests; management pagination keeps
  batch scope intact. No live paid-model routing accuracy claim is made.
- Settings: async App tests passed and production build emits a separate settings
  chunk. Initial JS remains above the bundler warning threshold.
- Backend boundaries: unchanged migration SQL/transactions, 850 tests passed,
  3 skipped. RunManager task ownership unchanged.
- Version 0.19.0: 35 version/contract tests, compileall, lock and dependency checks
  passed. Windows installer isolation passed; no real Linux execution claimed.
- In-app browser with isolated real Skills UI: desktop width 1428 and mobile
  width 390 had no horizontal overflow; page two rendered 20 rows beginning at
  Skill-20, final page five rows beginning at Skill-40. Viewport override reset.
- No production install, push, user-data mutation or automatic commit.

The chronological checkpoints above describe intermediate states, not remaining
work. Network Skills lists still return the complete catalog; only rendering and
model discovery are paginated. Real provider routing quality is not established
by deterministic gateway tests and remains a separate measurement.
