# Skills automatic inheritance — 0.17.0

## Behavior

- One backend resolver controls management views and immutable Run snapshots.
- NFC/casefold names select workspace registrations before checking availability.
- Disabled, missing, invalid and inaccessible local registrations block same-name globals.
- External names are re-read; same-scope collisions fail closed for all candidates.
- Deletion restores global inheritance; selected IDs cannot bypass shadowing.

## Migration and interface

- Atomically migrate catalog v1/v2 to v3, retaining switches and removing manual overrides.
- Keep old journal recovery readable without a writable legacy API.
- Add shadowedBySkillId and shadowed_by_workspace; remove workspace-override and disabledWorkspaces.
- Workspace settings show read-only global inheritance, replacement and no-fallback hints.
- Version 0.17.0, README and OpenAPI updated. No installed data, push or deployment.

## Verification

- Full backend: 835 passed, 3 skipped (`pytest -p no:cacheprovider -W error -q`).
- Full frontend: 336 passed / 43 files; typecheck and production build passed.
- Python compileall, uv lock --check --offline, uv pip check and git diff --check passed.
- Old single-file and package journals tested against both legacy catalog versions.
- No installed-runtime/browser visual or real Linux execution claim; no deployment or push.
