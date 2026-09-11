# Schedule settings layout

## Scope

- Keep the existing palette and schedule execution policy. No backend, version,
  installation, or credential changes.
- Replace expanded schedule cards with a compact single-column list. Keep names,
  workspace, cadence/time zone, next execution and latest result visible; collapse
  prompts and execution details.
- Add NFC/case-insensitive name search, workspace/status filters and 20-item
  pagination. Follow the existing API cursors so search includes all schedules,
  rather than only the first 100. Reject repeated cursors and ignore stale reads.
- Use enable switches, edit icons and a more menu for run/history/conversation/
  removal. Completed schedules have no enable switch. Removal requires confirmation.
- Group the editor into task, time and execution sections; collapse advanced
  execution settings without resetting their values. Label local input and
  displayed timestamps explicitly.
- Separate history loading, failure and empty states; add retry, trigger and
  start/finish timestamps. A successful mutation followed by a failed refresh
  is reported as saved with stale data, not as a failed mutation to repeat.
- Add Traditional Chinese, English and Japanese labels and responsive styles.

## Verification

- Full frontend suite: 55 files, 482 tests passed.
- TypeScript typecheck and production build passed; existing large-bundle warning
  remains. JSDOM emits existing pseudo-element computed-style warnings.
- Tests cover filters/search/pagination, completed state, preserved advanced
  values, history errors/retry, cursor encoding and traversal, duplicate mutation
  prevention, stale-response ordering, and save-success/refresh-failure handling.
- Desktop browser preview at localhost:5174, 1329px: settings page, empty state,
  create form sections and cancel inspected; no horizontal page overflow.
- No real schedule was created, run, changed or removed. Populated list behavior
  is covered by component tests, not a live-data browser run. Real mobile and
  200% zoom visual verification remain outstanding; responsive editor behavior
  is covered by component tests.
- Backend scheduling engine unchanged; backend suite not rerun for this UI slice.

## Delivery

Source changes only. No version bump, commit, push or installed-runtime update.
