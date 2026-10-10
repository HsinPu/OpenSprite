# Core/product boundary integration verification

- Product version: `0.21.43` -> `0.21.44`.
- Scope: integration evidence for product Prompt rendering/optional recording,
  explicit preparation, dependency assembly and preserved public SDK v5.
- Branch: `codex/core-runtime-hardening`.

The core executes only explicitly prepared inputs and supplied Loop, gateway
and repository capabilities. Product templates, language/time/workspace
lookup, Provider capability lookup, recording policy, discovery and background
dispatch are composed outside the engine. The product installs HTTP,
credentials, management and official Loops through its `app` extra. The plain
core wheel has no third-party runtime requirements. All these facilities still
ship in one backend distribution; this stage establishes dependency/import
boundaries rather than splitting every product module into a separate wheel.

Host cancellation, deadline/hard caps, snapshot provenance, pinned base prefix,
durable event/context receipts and terminal SQLite transactions remain
mandatory. Optional full Prompt files cannot replace these guarantees. A
bounded asynchronous recorder drops optional work on overload/failure and emits
sanitized diagnostics. It does not guarantee full debug receipts after process
death, a blocked disk or a full queue. SDK v5 and the original author wheel are
unchanged; Python plugins still run in the same trusted process.

Verification results:

- Full backend: **1,053 passed** on Linux, warnings as errors, plus compileall,
  lock check and pip compatibility. Frontend: **482 passed**, TypeScript and
  production build. These complete suites used `0.21.43`; all **128 backend
  and official Loop Python sources** exactly match the delivered `0.21.44`
  image and current workspace after newline normalization.
  The final native core-isolation/v5-contract check passed **7 tests**, and
  final `0.21.44` compileall, lock and backend venv compatibility checks passed.
- Final `0.21.44` wheel: normal offline installation in a fresh venv without
  `--no-deps`; only the backend is installed. A randomized custom Loop runs
  through actual Host and SQLite. Normal installation of the unchanged
  `0.5.0` example adds only that wheel; its three-step flow runs with no
  official Loop or HTTP/credential/management packages. Both match the v5
  golden contract. These fixtures make no network calls.
- Windows PowerShell 5.1: installer safety tests, actual isolated installation,
  official Loop import, metadata and uninstall preserving fixture data passed.
  Linux UID 10002: actual installation in a path containing spaces, access
  helper and generated systemd user unit validation passed. The Linux test
  intentionally does not start/register/uninstall a real user service.
- Docker UID 10001: workbench wheel import only caches; its generated bundle
  installs the identical old wheel, validates file hashes/provenance and yields
  a verified runtime manifest. The deployed author ZIP exactly matches all
  nine canonical sources, including updated author instructions.
- Actual OpenRouter HTTPS, requested model `openrouter/auto`: three Loops,
  **5 paid model requests**. Each new task uses a random nonce and varying
  arithmetic; answers match both. Standard/no-recovery write no optional
  Prompt files. Example review writes one System Prompt and three complete
  model request receipts with pinned prefix, actual variable input and
  UID 10001/mode 0600. Private drafts stay outside conversation messages.
- SSE, pinned execution profile, mandatory context receipts, token usage,
  request replay and complete run/step/event/message state were checked.
  Restart preserves all three tasks; replay adds no model requests.
- A separate network-disabled container mounts its logs volume **read-only**.
  Both actual file writers fail; a randomized protocol task still completes,
  mandatory SQLite state persists, and diagnostics contain no Prompt.
- Four actual SIGKILL cases (answer/draft streaming, summary/final transaction)
  preserve committed state and roll back incomplete transactions. A second
  restart is identical. Unflushed deltas and power-loss durability are outside
  this verification.
- Browser: rendered settings inspected at desktop 1280x720, tablet 768x1024
  and mobile 390x844. Updated recording text wraps, controls remain usable,
  mobile navigation works and no browser warning/error logs were reported.
  Execution settings show all three v5 Loops and the verified wheel manifest;
  About shows `0.21.44`. Temporary viewport override was reset.

Public non-secret results are in
`0328-core-product-boundary-evidence.json`. The test Gateway/MockTransport
checks are explicitly separate from actual paid HTTPS execution. Existing
example wheel SHA-256:
`e75ed2849b131bf3c051885e6d68a290856a168b662d9a7c7df60b01b0c9b4b3`.

Owned local preview: `http://127.0.0.1:18771`, image
`opensprite:product-boundary-with-example`. The original preview image was
retained as `opensprite:rollback-core-product-0.21.40`; its data volume was
reused without deletion. The separate main service on port 8765 remains on its
original image. No merge into main is part of this change. Docker's existing
development build-info fallback remains; image/source identities are recorded
in this verification rather than inferred from that UI label.

Future changes should follow actual capability needs: a separately versioned
SDK if the base-prefix contract changes, finer product packaging if separate
consumers need it, or process isolation for untrusted plugins. They are not
prerequisites for this import/dependency boundary.
