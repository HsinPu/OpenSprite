# 0010 - Secure provider validation runtime

## Objective

Implement the already-approved Provider Connections HTTP contract behind its
dependency seam without changing endpoint shapes, provider order, public error
envelopes, or the exact-backend-pinned credential-store policy.

## Security boundary and invariant

The attacker-controlled input is the PUT `apiKey`; provider responses and the
local metadata file are also untrusted. The affected assets are the prior OS
credential, connection status, and local secret-bearing process memory. The
enforcement point is `ProviderConnectionService`, not an individual route, so
PUT, POST test, DELETE, and GET share one fixed catalog and one transaction
policy.

- Only `openai` and `anthropic` adapters exist.
- Candidate keys are validated before local mutation.
- Redirects are disabled, TLS verification remains at the `httpx` default, and
  each provider request has a fixed 30-second timeout.
- A provider success is accepted only when its body is at most 1 MiB and its
  JSON object contains a `data` list. The list and response body are discarded.
- 401/403 map to `invalid_credentials`, 429 to `provider_rate_limited`, timeout
  to `provider_timeout`, and transport/5xx/malformed success to
  `provider_unreachable`. Other non-2xx responses conservatively map to
  `provider_unreachable`; they are not treated as proof of invalid credentials.
- The keyring remains the only secret store. Non-secret JSON metadata contains
  provider id, public status, display-only credential preview, UTC check time,
  and an internal full SHA-256 fingerprint that binds state to the complete
  credential. The fingerprint is never included in the public summary.
- Metadata uses a strict version-2 schema, the fixed provider catalog, the
  then-current application-data location, and atomic same-directory
  replacement. Corrupt or unavailable
  metadata fails closed; schema v1 is rejected with no legacy lookup, fallback,
  or migration.
- Provider mutations use per-provider async locks under the single-process
  desktop ownership assumption. Local writes are re-read for proof. A partial
  failure restores both prior secret and prior state when possible and never
  returns success, even when rollback cannot be proven.
- POST test is a state-only transaction. It reads the credential for provider
  validation and verification but never calls credential set/delete. A state
  failure restores only prior state and re-reads the credential to prove it is
  unchanged.
- No error or log includes a credential, request header/body, upstream body, or
  upstream exception text.

## Code and dependency changes

- Promoted `httpx==0.28.1` to a runtime dependency.
- Added the then-current application-data path dependency; the centralized
  path contract in change 0013 later superseded and removed it.
- Added fixed HTTP provider adapters and offline `MockTransport` tests.
- Added strict atomic JSON provider-state repository.
- Bound metadata to the full credential using an internal SHA-256 fingerprint;
  preview remains presentation-only.
- Added a bounded 1 MiB streaming reader for provider success bodies.
- Replaced the unavailable-only service seam with transactional orchestration
  while preserving `UnavailableProviderConnections` as `create_app()`'s safe
  default.
- Added `create_provider_runtime()` and `ProviderRuntime.aclose()` for a future
  server-launch owner. This slice does not add a CLI or activate the runtime.

## Verification

All tests use fake credential/state stores and `httpx.MockTransport`; no real
provider or OS credential operation is performed. Final evidence on Windows,
Python 3.12.13:

- focused provider/security suite: **65 passed**;
- `uv run pytest -W error --basetemp .pytest-tmp`: **140 passed**;
- `python -m compileall -q src tests`: passed;
- `uv lock --check --offline`: resolved the locked 34-package graph without
  network access;
- `uv pip check`: checked 29 installed packages, all compatible;
- secret-boundary source scan: no logging, telemetry, response-body error, or
  plaintext fallback path exists in the provider runtime; and
- `git diff --check`: passed.

No dedicated security scanner is configured in this backend, so no broader
SAST or dependency-vulnerability result is claimed.

## Rollout and follow-up

Provider routes remain fail-closed by default until a later server-launch slice
owns runtime creation, shutdown, loopback binding, Host validation, and
same-origin mutation enforcement. Those controls remain release-blocking. On
deployment, monitor only aggregate fixed error codes and operation counts; do
not log request bodies, headers, provider bodies, or exception text. No
credential rotation or incident action is required for this implementation-only
slice because tests never used real credentials and the runtime was not
activated.
