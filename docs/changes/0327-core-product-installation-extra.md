# Core wheel and complete product installation

- Product version: `0.21.42` -> `0.21.43`.
- Scope: remove mandatory product/official Loop dependencies from the core
  wheel while preserving complete desktop and Docker installations.

The base backend has no third-party runtime requirements. The `app` extra owns
the official Loop and the existing HTTP, credential, authentication and platform
dependencies. Docker and Windows/Linux installers explicitly install this
extra from the locked product graph. Current development and author verification
instructions also select the extra on both sync and run commands. Historical
change records remain untouched. Docker uses a uv build cache for repeated
versioned validation builds; runtime ownership remains UID 10001.

The new installed-core verifier uses a fresh venv and normal offline dependency
resolution, asserts that only the core package is installed, and runs real
Host/SQLite execution with variable protocol data. It then normally installs
the unchanged author wheel and verifies the v5 golden ABI and three-step flow
without official Loop or product dependencies. Both installations and real
Host/SQLite executions passed. Only `opensprite-backend` was installed for the
first run; only it and `opensprite-execution-example` were installed for the
three-step run. The old example wheel SHA-256 stayed
`e75ed2849b131bf3c051885e6d68a290856a168b662d9a7c7df60b01b0c9b4b3`.

The complete Linux backend suite passed **1,053 tests**, with warnings treated
as errors. Compileall, locked dependency validation and pip compatibility checks
passed. The frontend passed **482 tests**, TypeScript and production build.
The Windows PowerShell 5.1 installer suite passed, including an actual isolated
installation, official Loop import and uninstall preserving fixture user data.
The initial PowerShell 7 invocation exposed an existing process-policy test
assumption; the supported 5.1 runner passed without changing persistent policy.
The unchanged example passed **3 source tests** and the installed-wheel
Host/provider-adapter/SQLite/cancellation verifier. Those adapter tests use
variable protocol data with a MockTransport; actual HTTPS model and Linux
non-root installer verification are recorded in the final integration stage.
