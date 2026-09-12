# Execution diagnostics implementation checkpoints

## Scope and baseline

- User approved all four phases, with tests required before moving to the next phase.
- Baseline: c5283faf. Working tree was clean; no empty pre-work commit was created.
- Preserve context capacity, compaction thresholds and retry eligibility/count policies.
- No automatic push, release bump, or installed-runtime deployment.
- Do not inspect private user conversations or credentials for test fixtures.

## Phase gates

1. Automated gate passed: compaction lifecycle events, unique operation identity, truthful UI terminal states, cancellation/interruption and repeated-operation handling. Backend 83 tests, API contract 7 tests, frontend 38 tests and TypeScript passed. Rendered browser review remains part of the final gate.
2. Automated gate passed: logical request and attempt identity, purpose, retry cause, compaction linkage. Backend phase 1+2 and contract suite 93 passed; frontend 40 passed; TypeScript passed. Tool follow-up versus retry, continuation limits, failed/cancelled attempts and concurrent scope isolation covered. Detailed presentation follows in phase 4.
3. Automated gate passed: safe context source receipts, effective budget and estimated contribution breakdown. Backend 95 passed; frontend 42 passed; TypeScript passed. Receipts are checked against actual gateway inputs, component sums, private-field rejection, and unknown provenance.
4. Implemented: paginated historical diagnostics, expandable details, loaded-page redacted export and hash-based comparison with existing opt-in full prompt receipts. Focused backend 83 passed; migration/MCP selection 77 passed; frontend paging, redaction, run switching and focus checks passed. Actual synthetic browser review covered desktop/tablet/mobile and corrected narrow-screen clipping and nested-drawer keyboard handling. See 0281 for boundaries.

## Final gate

- Run affected backend and frontend regression suites, TypeScript, production build and diff checks.
- Exercise actual rendered diagnostic interactions with synthetic data.
- Document exact passing checks and remaining limitations; never infer success from a started event.
- Each phase must pass its gate before implementation expands to the next phase.

## Current inspection

- Existing event storage validates event payloads and SQLite schema versions; new lifecycle types must be admitted consistently across backend, storage and frontend contracts.
- Existing compaction-start payload is empty, and the frontend currently collapses repeated starts and can infer completion incorrectly.
- First implementation slice will add lifecycle contracts and focused tests before changing the producer and renderer.

## Final regression results

- Backend: 1,100 passed, 3 skipped, 4 deselected. The four deselections are
  verified pre-existing hardcoded 0.21.0 version tests; HEAD is already 0.21.13.
  Their names and evidence are recorded in 0281. No version test or version
  number was changed to hide this baseline mismatch.
- TypeScript, production build, Python compileall and git diff checks passed.
- Frontend final regression: 61 files and all 520 tests passed after the focus
  correction, with no source changes during that final run.
- Installed runtime, user data, package versions and Git remote remain unchanged.
