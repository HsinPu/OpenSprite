# OpenSprite repository instructions

## Current direction

- OpenSprite is being rebuilt from a clean repository foundation.
- The repository now contains a runnable React frontend and a minimal Python
  backend for local Provider connections and encrypted credential persistence.
- Continue to add backend capabilities only from an explicitly approved
  frontend workflow or contract; do not restore speculative archived behavior.
- Do not add an application CLI, command shim, Typer, Click, or argparse command suite.
- The archived implementation at `codex/archive-main-before-refactor-20260820` is read-only reference material. Never restore it wholesale.

## Repository boundaries

- `frontend/` owns browser UI source, frontend tests, and frontend build configuration.
- `backend/` owns the Python local service, encrypted persistence adapters and
  backend tests.
- `contracts/` owns authoritative frontend/backend HTTP and future WebSocket
  contracts.
- `installers/` will own separate Linux and Windows installation implementations with matching behavior.
- `docs/architecture/` records durable architecture decisions.
- `docs/changes/` records every implementation slice and its verification evidence.
- `scripts/` is reserved for repository verification and maintenance automation.

Keep business behavior out of shared configuration, installer, and documentation boundaries. Do not create generic dumping grounds such as broad `utils`, `helpers`, or `services` directories.

## Local user-data boundary

- `%USERPROFILE%\.opensprite` on Windows and `~/.opensprite` on Linux are the sole OpenSprite user-data roots.
- All future conversations, databases, uploaded attachments, generated outputs, memory, state, logs, and cache must remain below that root and use the mapping owned by `backend/src/opensprite_backend/app_paths.py`.
- Do not introduce a second product-data root, persist absolute user-profile paths in the database, or let individual features construct their own home-directory paths.
- Program installation remains separate. Provider API keys are stored only as
  AES-256-GCM ciphertext in `.opensprite/auth.json`, using the random
  per-install key in `.opensprite/config/credential.key`.
- Never add plaintext credential persistence, OS-keyring fallback, a fixed
  application-wide encryption key, secret logging, or API responses containing
  raw credentials. Treat the complete `.opensprite` root as sensitive because
  possession of both encrypted data and `credential.key` permits decryption.
- Backup, restore, move and delete `auth.json` and `credential.key` together.
- Only one desktop backend process may write a user-data root; do not enable
  multiple Uvicorn workers or a reloader against one `.opensprite`.
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
npm test -- --run
npm run typecheck
npm run build
npm run dev
```

Backend checks:

```powershell
cd backend
uv sync --dev
uv run pytest -W error
uv run python -m compileall -q src tests
uv lock --check --offline
uv pip check
```

Repository checks:

```powershell
git diff --check
git status --short --branch
```

Browser verification remains manual against the local Vite server. Frontend,
backend and API contract tests are committed; installer execution tests do not
exist yet and must not be claimed.

## Generated and local files

- Commit `frontend/package-lock.json` whenever frontend dependencies change.
- Never commit `node_modules`, `dist`, Python virtual environments, caches,
  logs, `.opensprite`, `auth.json`, `credential.key`, raw credentials, `.codex`,
  or `.codegraph`.
- `.agents/` is intentionally not ignored so future repository skills can be reviewed and committed deliberately.
- Never delete user data, credentials, databases, or installation directories without explicit approval and verified absolute paths.
