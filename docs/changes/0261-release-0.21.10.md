# Release 0.21.10

- Synchronize backend metadata, lockfile, and README from 0.21.9 to 0.21.10.
- Include the Tools settings layout described in change 0260 and the preceding General settings improvements.
- No dependency or backend behavior changes.
- Frontend verification from change 0260: 456 tests passed, typecheck and build passed.
- Local Windows update requested by the user; use the official installer and verify health and installed version after installation.
- No commit or push requested.

## Local verification

- `uv lock --check --offline` and `git diff --check` passed.
- Official Windows installer completed successfully with `Started: True` and version `0.21.10`.
- `/healthz` returned `ok`; `/api/app-info` reported installed version `0.21.10` and revision `dd3b9f50` with local uncommitted changes.
- Installer reported a locked temporary rollback directory (`PreviousCleanupComplete: False`). Preserved it rather than forcing deletion; application health passed.
