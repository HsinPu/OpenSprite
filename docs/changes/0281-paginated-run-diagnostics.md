# Paginated execution diagnostics

## Behavior

- Add `GET /api/runs/{run_id}/event-history` with an ascending sequence cursor,
  a maximum page size of 100, and one-row lookahead. This does not alter SSE
  replay or the bounded live event buffer.
- Add an on-demand Ant Design diagnostic drawer to the execution panel.
  Previous/next replaces the loaded page rather than accumulating an unbounded
  history. Run changes and closing invalidate outstanding requests.
- Expand a diagnostic event to inspect request/attempt/compaction identifiers,
  timestamps, safe source receipts, conservative token estimates, and actual
  usage when reported. A start is not presented as a completed operation.
- JSON export is explicitly **the loaded page only**. It allowlists validated
  attempt and compaction metadata, excludes message/tool contents, and does not
  assert that an active run is complete. Unknown provider usage remains null.
- Existing opt-in full prompt files include the same normalized request hash
  and complete tool definition schemas. Hash plus run identity allows manual
  comparison with diagnostic records. This does not enable full logging or
  add an endpoint that downloads private prompt files. Compaction requests do
  not gain full prompt logging through this change.
- Authentication and no-store headers use existing application middleware.
  No new credential, filesystem path, or remote telemetry surface is added.

## Verification and corrections

- Phase 4 focused backend suite: 83 passed, including HTTP pagination beyond
  500 events, query bounds, not-found, unauthorized access, replay semantics,
  source receipts, attempt traces, compaction lifecycle and prompt-hash linkage.
- Updated migration/MCP/app-route regression selection: 77 passed, one existing
  version test deselected. The old provider migration fixture is explicitly
  stamped v15 before testing its rollback; its target remains v16.
- Browser fixture: `frontend/tests/diagnostics-preview.html`, served by local
  Vite. It replaces fetch with synthetic responses and never contacts the real
  backend or reads user conversations.
- Actual browser checks at 390x844, 768x1024 and 1440x900: open, paging,
  expandable metadata, long identifiers and close. No captured console errors.
- Browser review caught the fixed-width drawer exceeding a narrow viewport;
  constrained its wrapper to 100vw. Regression testing caught closed nested
  drawers intercepting the outer mobile drawer Escape event; mount only while
  open. Explicitly restore focus to the diagnostic trigger on close.
- TypeScript, production build and Python compileall passed. Build retains a
  large-chunk warning; no dependency or version changes were made.

## Baseline test limitation

The first full backend run reported 1,094 passed, 9 failed and 3 skipped.
Five failures required synchronization with this change and were corrected.
Four unrelated baseline tests hardcode version 0.21.0 while HEAD already has
0.21.13 in pyproject.toml (verified with git show):

- test_app_info_uses_the_package_version
- test_product_version_has_one_authoritative_value
- test_development_info_uses_package_version_without_writing
- test_installed_info_requires_matching_package_version

These tests and the product version are intentionally unchanged. Final rerun:
backend 1,100 passed, 3 skipped, 4 baseline version tests deselected; frontend
61 files / 520 tests passed. The final source also passed TypeScript, build,
Python compileall, and whitespace checks.

## Limits

This is normalized gateway-request tracing, not provider-internal HTTP retry
tracing or a wire-payload capture. The historical drawer is paginated, not a
whole-run export. Old records without metadata remain old records; no source
or outcome is fabricated. Full receipts remain local and opt-in.
