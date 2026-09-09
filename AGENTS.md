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

Windows installer checks:

```powershell
./installers/windows/test.ps1
```

Browser verification remains manual against the local Vite server or installed
single-origin runtime. Frontend, backend, API contract and Windows installer
isolation tests are committed; Linux installer execution tests do not exist yet
and must not be claimed.

## Generated and local files

- Commit `frontend/package-lock.json` whenever frontend dependencies change.
- Never commit `node_modules`, `dist`, Python virtual environments, caches,
  logs, `.opensprite`, `auth.json`, `credential.key`, raw credentials, `.codex`,
  or `.codegraph`.
- `.agents/` is intentionally not ignored so future repository skills can be reviewed and committed deliberately.
- Never delete user data, credentials, databases, or installation directories without explicit approval and verified absolute paths.

<!-- SYMBOL_LATTICE_START -->
## SymbolLattice

Guidance version: `0.513.0`

### Activation and indexing

- Before relying on version-sensitive behavior, run `SymbolLattice --version`. If it differs from the guidance version, report the mismatch and refresh the Codex installation.
- A repository is queryable only when its resolved root contains `.SymbolLattice/index.sqlite`. A `.SymbolLattice` directory alone does not prove that an index exists.
- When a task requires locating, understanding, reading, or changing source code, resolve the repository root and run `SymbolLattice status . --json` before broad exploration.
- If an expected `SymbolLattice` CLI command is reported as not found or its installed entrypoint appears missing in a sandboxed shell, do not conclude that SymbolLattice is uninstalled from that symptom alone. When MCP is unavailable, retry the same command once through the host's sandbox escalation mechanism only if that exact command and project scope were already authorized. Do not replace it with `init`, `index`, `sync`, install, upgrade, or another write-capable command unless that mutation was already authorized. If escalation is unavailable, denied, or the retry still fails, report the sandbox access boundary once and fall back to targeted `rg` and direct file reads.
- Treat one outer `.git` repository as one monorepo, even when it contains multiple packages. Treat a directory containing independent repository or manifest roots as a workspace container, not as a repository.
- In a workspace container, discover relevant repository roots through declared workspace members and child directories at most two levels deep. Skip hidden metadata, dependencies, generated output, caches, archives, and temporary directories.
- If a relevant repository has no `.SymbolLattice/index.sqlite`, run `SymbolLattice init .` automatically from that repository's resolved root and briefly tell the user that a local index is being created.
- Never initialize a filesystem root, home directory, Desktop root, temporary directory, dependency directory, generated-output directory, or a parent directory that contains multiple unrelated projects.
- For multi-repository tasks, query every relevant repository separately with its own `projectPath`. Combine project-scoped findings without claiming cross-repository edges.
- If automatic initialization fails or cannot be performed, report the reason once and fall back to targeted `rg` and direct file reads. Live MCP graph reads enforce strict freshness internally: they synchronize under writer authority or return `FRESH_INDEX_REQUIRED`/`PROJECT_NOT_STABLE` without stale evidence. Report that failure before a targeted raw-source fallback. Never run `index` or rebuild an existing index unless the user explicitly requests it.

### Query routing

- Use `SymbolLattice_explore` before Read, Grep, or broad file reads for any task that locates, explains, reads, or changes indexed code. Include the question plus relevant file or symbol names when known.
- Treat source returned by explore as already read. Do not repeat the same discovery with filesystem tools; refine the explore query when more indexed detail is needed.
- Use optional specialist tools only when the client lists them. If MCP is unavailable, use the equivalent `SymbolLattice` CLI command from the repository root.

### Evidence and safety

- Treat exact symbols, source ranges, and edges as evidence. Treat pending, unresolved, ambiguous, truncated, or low-confidence results as incomplete.
- When graph evidence conflicts with the current working tree, verify the current files directly and state the mismatch.
- Do not edit files inside `.SymbolLattice` manually. Treat the directory as generated local state and do not commit it unless repository policy explicitly requires it.
<!-- SYMBOL_LATTICE_END -->
