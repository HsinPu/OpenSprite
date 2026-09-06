# 0.12.1 — Managed workspaces under the product data root

- AppPaths now owns `.opensprite/workspace`; removed service-level home fallback.
- Kept external mounts denied access to app data; added separate managed-child
  inspection and ancestry link/reparse checks for provisioning and import.
- Catalog v3 identifies the new layout. v2 registered roots are copied and
  SHA-256 verified with a restart journal; source files are never removed.
  v1 still converts external roots to mounts without moving them.
- Collisions and copy/write failures keep the catalog unchanged, show a
  localized migration warning, and retry on reload. Missing roots stay missing.
- Run recovery precedes relocation; scheduler starts afterwards. Historical
  Run snapshots and SQLite schema remain unchanged. Catalog mutation is blocked
  on relocation failure. In-flight relocation completes before cancellation.
- Windows installer allows five minutes for startup. Very large copies may
  exceed that wait; the source remains intact and backend progress can complete.
- Skill loading remains a future feature; no installed user data was modified
  while developing or testing this change.

## Verification

- Full backend: 727 passed, 3 skipped; subsequent added relocation boundary
  tests: 9 passed, 1 skipped. The extra skip requires OS symlink privileges.
- Full frontend: 280 passed; added relocation-response test: 4 API tests passed.
- Typecheck and production build passed (existing bundle-size warning).
- compileall, offline lock check and dependency check passed.
- Windows installer isolation passed; locked test binaries were quarantined by
  the existing test cleanup procedure.
- Git diff whitespace check passed with the repository's normal CRLF settings.
- User-authorized Windows update verified 0.12.1 and healthy HTTP service.
  Default and test workspaces report the new data-root paths as available;
  all nine conversations and both original directories remain present.
  A locked previous-install rollback directory was retained by the installer.
- Real Linux GUI/systemd remains untested.
