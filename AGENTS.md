# OpenSprite repository instructions

## Current direction

- OpenSprite is being rebuilt from a clean repository foundation.
- Work frontend-first. Do not add backend runtime code until the user explicitly starts the backend phase.
- Do not add an application CLI, command shim, Typer, Click, or argparse command suite.
- The archived implementation at `codex/archive-main-before-refactor-20260820` is read-only reference material. Never restore it wholesale.

## Repository boundaries

- `frontend/` owns browser UI source, frontend tests, and frontend build configuration.
- `backend/` is reserved for the future Python service and its tests.
- `contracts/` will own explicit frontend/backend HTTP and WebSocket contracts once those interfaces are designed.
- `installers/` will own separate Linux and Windows installation implementations with matching behavior.
- `docs/architecture/` records durable architecture decisions.
- `docs/changes/` records every implementation slice and its verification evidence.
- `scripts/` is reserved for repository verification and maintenance automation.

Keep business behavior out of shared configuration, installer, and documentation boundaries. Do not create generic dumping grounds such as broad `utils`, `helpers`, or `services` directories.

## Local user-data boundary

- `%USERPROFILE%\.opensprite` on Windows and `~/.opensprite` on Linux are the sole OpenSprite user-data roots.
- All future conversations, databases, uploaded attachments, generated outputs, memory, state, logs, and cache must remain below that root and use the mapping owned by `backend/src/opensprite_backend/app_paths.py`.
- Do not introduce a second product-data root, persist absolute user-profile paths in the database, or let individual features construct their own home-directory paths.
- Program installation remains separate. Raw API credentials remain in the operating-system credential service and must not be written under `.opensprite`.
- Do not create reserved directories until an implemented feature performs its first real write.

## Change workflow

1. Keep each change focused on one approved objective.
2. Update or add a matching record under `docs/changes/` in the same commit.
3. Add abstractions only when current behavior requires them.
4. Run the narrowest real verification that exists, followed by broader checks when available.
5. Use English Conventional Commit subjects and create one independently reviewable commit per slice.

Do not add compatibility aliases, disabled legacy paths, keyword-based task routing, or speculative lifecycle layers unless a new approved requirement explicitly needs them.

## Current verification

The frontend now contains a runnable fake-data demo. Run these frontend checks:

```powershell
cd frontend
npm ci --ignore-scripts
npm run typecheck
npm run build
npm run dev
```

Repository checks:

```powershell
git diff --check
git status --short --branch
```

Browser verification is currently manual against the local Vite server. Do not claim that automated frontend tests, backend tests, API tests, or installer tests exist until their implementing files and commands are committed.

## Generated and local files

- Commit `frontend/package-lock.json` whenever frontend dependencies change.
- Never commit `node_modules`, `dist`, Python virtual environments, caches, logs, credentials, `.codex`, or `.codegraph`.
- `.agents/` is intentionally not ignored so future repository skills can be reviewed and committed deliberately.
- Never delete user data, credentials, databases, or installation directories without explicit approval and verified absolute paths.
