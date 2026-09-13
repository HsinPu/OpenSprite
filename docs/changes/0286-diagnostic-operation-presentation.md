# Diagnostic operation presentation

## Scope

- Group validated attempt events by run ID and attempt ID; group compaction by run ID and compaction ID. Summary model calls remain separate. Preserve raw export contracts and legacy uncorrelated records.
- Stable operation keys retain disclosure state when a later page supplies the terminal event. Duplicate sequences do not produce duplicate rows. Incomplete history and unavailable terminal records are explicit, not assumed success or active execution.
- Compact result metadata, actionable credential guidance, nearby timestamps, and combined actual/estimated usage. Source breakdown and technical metadata are progressively disclosed; raw range/export notes are collapsed.
- Container-based layout uses one column in narrow drawers and two usage columns when wide. Existing colors, resize edge, pointer capture and keyboard behavior are preserved.
- Extract the shared resize control into `src/ui/PanelResizeHandle.tsx`; app sizing policies remain in app. This repairs an existing uncommitted chat-to-app dependency violation without weakening architecture checks.

## Verification

- Initial focused tests: 19 passed; TypeScript and production build passed.
- Final focused tests (operation grouping, UI, resize, architecture): 23 passed. A test's over-specific accessible-name whitespace matcher was corrected; the behavioral assertion still verifies terminal status, a single row, and retained expansion.
- The UI boundary is explicitly checked: shared UI cannot depend on app/features. No architecture allowlist exception was added for chat-to-app imports.
- Full parallel run exposed the resize dependency violation and App/Schedule timing failures. App/Schedule isolated rerun: 45 passed; full single-worker rerun performed after boundary repair.
- Single-worker full run: 532 passed, one failed using the pre-correction accessible-name matcher already loaded by that process. After correcting that matcher, all 23 focused tests passed. The full suite was not restarted after that test-only correction; do not claim a fully green single invocation.
- Browser synthetic fixture: started/terminal pagination merges into one expanded row; raw diagnostics are not replaced by grouped data.
- Browser default 560px drawer and dragged 860px drawer: nearby time, preserved expansion, two usage columns at wider size, no document horizontal overflow.
- Mobile override 390px (433 CSS px at browser zoom): full-width drawer, no resize handle, single-column usage, no horizontal overflow.
- Existing jsdom pseudo-element warning and Vite chunk-size warning remain.
- No live model request or credential mutation; synthetic success does not establish provider health. No version bump, commit, push or installed-runtime update.
