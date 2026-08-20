# Change 0009: secure OS credential store

## Objective

Add the isolated persistence boundary for one API key per fixed provider without
making provider routes operational or adding provider network behavior.

## Security boundary

Caller-controlled provider IDs and candidate secrets cross into the credential
store. Only `openai` and `anthropic` are accepted, each maps to one fixed name in
the `OpenSprite` service namespace, and blank secrets are rejected before any
keyring call. The adapter accepts only Windows Credential Manager through
`WinVaultKeyring` or Linux Secret Service through `SecretService.Keyring`.
Missing, overridden, unsupported, or failing backends fail closed with fixed
internal errors that do not include backend details or secret text.

There is no credential enumeration, generic key/value API, custom service name,
filesystem persistence, plaintext fallback, migration behavior, CLI, provider
request, or HTTP route wiring in this slice.

## Implementation

- Added the synchronous `CredentialStore` protocol with `get`, `set`, and
  idempotent `delete` operations.
- Added an injectable `KeyringCredentialStore` and a no-write `preflight()`.
- Operations run on the exact backend instance returned by preflight; they do
  not re-resolve keyring's mutable module-global backend.
- Backend exceptions are discarded before sanitized errors are raised, so
  internal errors retain neither a secret-bearing cause nor context.
- Pinned `keyring==25.7.0`. Its own platform markers bring
  `pywin32-ctypes` on Windows and `SecretStorage` plus `jeepney` on Linux.
- Added fake-facade security tests; they never access a real OS credential
  backend and are not OS integration evidence.

## Verification

- Focused credential-store tests with warnings as errors: `48 passed`.
- Full backend tests with warnings as errors: `75 passed`.
- Python bytecode compilation of `backend/src` and `backend/tests` completed.
- `uv lock --check --offline --project backend`: lock resolved consistently
  with 33 packages.
- `uv pip check --python backend/.venv/Scripts/python.exe`: 28 installed
  packages checked and compatible.
- Changed-scope pattern scans found no production filesystem, subprocess,
  logging, dynamic execution, plaintext-backend, or API-key-shaped values.
- `git diff --check` passed.

Commands:

```powershell
backend/.venv/Scripts/python.exe -m pytest -W error --basetemp backend/.pytest-tmp backend/tests/test_credentials_keyring_store.py
backend/.venv/Scripts/python.exe -m pytest -W error --basetemp backend/.pytest-tmp backend/tests
uv lock --check --offline --project backend
uv pip check --python backend/.venv/Scripts/python.exe
git diff --check
```

The dependency-vulnerability scanner was not installed and no vulnerability
database was fetched in this offline slice. A release gate should run SCA
against the committed lockfile before packaging.
