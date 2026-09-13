# Diagnostic UI hierarchy

## Scope

- Move the diagnostic entry into the execution-record heading as a labelled,
  tooltip-equipped Ant Design icon button. Opening it does not toggle the record.
- Reuse the existing Drawer/Collapse/Badge/Descriptions components and product
  colors. Narrow the drawer to 560px with a viewport maximum.
- Show run status, safe error text, model and completed duration when provided;
  do not infer a run result from a partial event list.
- Keep individual diagnostic events in sequence, with localized labels and
  timestamps. Disclose usage first and technical identifiers only on expansion.
- Distinguish unknown usage from zero, hide zero-valued source estimates by
  default, and provide identifier/hash copy controls.
- Append history using Load more. Preserve already loaded records on failure
  and retry the same cursor. Keep generation guards for closed/switched runs.
- Move export to More. Export only validated loaded diagnostic events, preserve
  existing content exclusion and completion non-assertion, and report failure.
- No backend behavior, credentials, model policy, dependencies, version, or
  installed-runtime changes.

## Verification

- Initial focused checks: 22 passed across 2 matching test files.
- Frontend full regression: 61 files / 522 tests passed.
- Final additional focused regression: RunDiagnostics 5 tests passed, including
  appended history, failed-page retry, stale response rejection, heading isolation,
  focus return, deferred export menu and unknown-vs-zero usage.
- Final TypeScript and production build passed. Existing chunk-size warning and
  jsdom pseudo-element getComputedStyle notices remain.
- Browser synthetic fixture (no provider requests or user-data access): record
  remained collapsed on icon click; details/technical disclosures and Load more
  worked; close returned focus to entry; no captured console errors.
- Browser viewport overrides 390x844, 768x1024, 1440x900 were inspected. Browser
  zoom was 90%, so effective CSS widths differed. DOM geometry confirmed no
  right-edge overflow for the narrow expanded technical view and desktop view.
  Capture output exhibited scaling/cropping artifacts; do not treat screenshots
  as pixel-perfect baselines. Viewport override was reset after checks.
- These are UI fixture checks, not a claim that successful live-provider
  compaction/retry flows have been reverified.
