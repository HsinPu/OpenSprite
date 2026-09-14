# Diagnostics synchronization and provider tool-policy validation

## Scope

Fix the reviewed stale diagnostics and misleading policy-save errors. No
provider transport, backend persistence, version, or installation changes.

## Diagnostics

- Poll the existing history endpoint every two seconds only while the drawer
  is open and the run is active. Use the last loaded sequence / pagination cursor.
- Serialize requests, merge by sequence, preserve loaded rows and expansion,
  and invalidate delayed responses on close or run changes.
- Capture the run status at request start. If the run ends during a request,
  fetch again after that request completes before diagnosing missing end events.
- Keep historical pagination explicit; partially loaded or failed refreshes do
  not imply a missing terminal event. Refresh/retry retains loaded data.
- Add a compact refresh action and live/final-sync explanation. Exported live,
  loading, or failed snapshots do not claim to cover current history.

## Provider policy

- Reuse the AI settings client's status/envelope validation, including distinct
  invalid-input, store, internal, network, and malformed-response errors.
- Trim and deduplicate model IDs without changing case. Validate empty IDs,
  256 Unicode code-point length, and the 1,000-ID limit. Backend validation stays
  unchanged and authoritative.
- Show errors next to the field, disable invalid saves, and preserve user input
  after API failures so saving can be retried.
- Maintain Traditional Chinese, English, and Japanese messages.

## Verification

- Stage 1 initial diagnostics regression: 30 tests passed.
- Stage 2 policy/API/validation regression: 20 tests passed; typecheck passed.
- Expanded combined focused suite: 52 tests passed.
- Full frontend suite: 64 files, 555 tests passed.
- Production build passed (existing large-chunk warning).
- Tests emit jsdom pseudo-element getComputedStyle limitations; no test failures.
- Browser used `tests/diagnostics-preview.html` with isolated synthetic fetches:
  observed running -> completed without reopening, expanded detail retained,
  final usage displayed, keyboard width changed 560 -> 570, and close restored
  trigger focus. Reviewed desktop and narrow screen states.
- Browser tool-policy check: a 257-character ID displayed field validation and
  disabled Save; replacing it with a trimmed ID restored Save. A synthetic 400
  showed the invalid-settings message, retained input, and a second save closed
  the modal successfully.
- No actual model call or live provider-setting write was made. This is rendered
  component / API-boundary validation, not a real-provider end-to-end claim.
- No local installation update, version bump, commit, or push.
