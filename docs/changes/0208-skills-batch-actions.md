# Skills batch actions — 0.18.0

Adds a trailing bulk-actions menu to the Skills toolbar: enable all, disable all,
and archive all. Actions apply only to the selected global or workspace scope;
inherited global entries remain read-only. The master switch is never changed.

`POST /api/skills/batch` accepts scope, workspaceId, action and expectedRevision.
Invalid enable candidates are skipped; unchanged entries are reported separately.
The response reports completed counts and per-item skipped/failed reason codes.
Revision conflicts require reload, not silent retries against a newer catalog.

Archive confirmation shows scope and count and requires localized confirmation
text. Files move to the managed archive, never permanent deletion. A version-3
archive journal records the original catalog and archive destinations; interrupted
operations roll forward before subsequent catalog access. I/O interruption returns
a storage error until recovery succeeds. This journal version is independent of
the unchanged version-3 Skill catalog.

Workspace disable preserves same-name shadowing. Removing workspace registrations
restores global inheritance for subsequent Runs. Existing snapshots are unchanged.

Verification: backend batch policy, authentication, strict requests, scope,
revision and interrupted archive recovery tests; frontend menu, confirmation,
cancellation, scope and duplicate-submit tests. No installed-runtime or real Linux
GUI verification is claimed. No push or local installation update is performed.

Final checks: backend 846 passed / 3 skipped (`-W error -p no:cacheprovider`,
because the existing pytest cache directory is access-restricted); frontend
346 passed; typecheck, production build, compileall, offline lock check,
dependency check and git diff check passed. Build retains the bundle-size warning.
Real browser interaction and Windows installer isolation were not rerun for this
settings-only slice; Linux GUI remains unverified.
