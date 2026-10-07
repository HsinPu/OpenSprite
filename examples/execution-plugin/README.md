# OpenSprite execution-plugin example

This is a pure-Python package for OpenSprite backend `>=0.21.27,<0.22`,
Python `>=3.12,<3.14`, and execution-plugin API v1. It contains no application
CLI, provider connection, credentials, persistent state, or direct tool access.

- `example_checkpointed`: an independent driver that resolves tool turns via
  the Host and returns the result issued by `host.finish`. It calls an extra
  checkpoint before and after each tool phase; it does not delegate to
  `StandardDriver` or return a fixed answer.
- `example_main_retry_only`: permits an otherwise eligible context retry only
  for the main model request's provider context-limit failure. It rejects
  recovery during continuation and rejects automatic output continuation.
  Core limits and approval requirements still apply.

The package is trusted Python code running with backend privileges. Static
wheel/metadata inspection does not sandbox it or prove its safety.

## Test and build from the repository root

Prepare the existing backend development environment first:

```bash
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml
uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin
```

The expected artifact is
`tmp/execution-plugin-wheel/opensprite_execution_example-0.1.0-py3-none-any.whl`.
Build output, caches and environments are local artifacts and are not committed.

## Use the downloaded example archive

The workbench download preserves `examples/execution-plugin/`, `docs/architecture/`
and the verification script under `scripts/`. It does **not** contain a backend
environment. Extract it into an empty development directory and run the commands
from that extracted root, rather than from `examples/execution-plugin/`.

To build the wheel, only Python and uv/build tooling are needed; building does
not download or install `opensprite-backend`:

```bash
uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin
```

To run unit tests or installed-wheel verification, use an existing compatible
OpenSprite **development/test** Python environment with pytest available. Do not
run `uv sync --project backend` in the extracted archive; there is no `backend/`.

```bash
OPENSPRITE_BACKEND_PYTHON=/ABS/opensprite/backend/.venv/bin/python
"$OPENSPRITE_BACKEND_PYTHON" -m pytest -c examples/execution-plugin/pyproject.toml
OPENSPRITE_PLUGIN_WHEEL="$(pwd)/tmp/execution-plugin-wheel/opensprite_execution_example-0.1.0-py3-none-any.whl" \
  "$OPENSPRITE_BACKEND_PYTHON" scripts/verify_execution_plugin_wheel.py
```

PowerShell equivalent:

```powershell
$taskBackendPython = 'D:/ABS/opensprite/backend/.venv/Scripts/python.exe'
& $taskBackendPython -m pytest -c examples/execution-plugin/pyproject.toml
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path ./tmp/execution-plugin-wheel/opensprite_execution_example-0.1.0-py3-none-any.whl).Path
& $taskBackendPython scripts/verify_execution_plugin_wheel.py
Remove-Item Env:OPENSPRITE_PLUGIN_WHEEL
```

The wheel verifier also needs uv on PATH, or its absolute executable path in
`OPENSPRITE_TEST_UV`. Unit tests never make model/provider calls or touch product
data. Use a disposable Docker test environment if the installed product does
not include development/test dependencies.

Verify that real wheel installation, rather than a source-directory import,
produces discoverable entry points and usable factories:

```bash
OPENSPRITE_PLUGIN_WHEEL="$(pwd)/tmp/execution-plugin-wheel/opensprite_execution_example-0.1.0-py3-none-any.whl" \
  uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

PowerShell equivalent:

```powershell
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path ./tmp/execution-plugin-wheel/opensprite_execution_example-0.1.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
Remove-Item Env:OPENSPRITE_PLUGIN_WHEEL
```

The verifier installs the wheel with `uv` into a temporary target directory,
uses a separate process to resolve it, and removes only that temporary target.
It never installs into the current backend environment or changes user data.

These tests use a scripted Host. They prove the example's control flow, factory
lifetime, policy decisions and installed-package discovery. They do not prove
provider behavior, actual Run acceptance, tool effects, cancellation persistence,
or Docker deployment. Core integration coverage remains in
`backend/tests/test_execution_plugin_integration.py`,
`backend/tests/test_execution_plugin_acceptance.py`, and
`backend/tests/test_agent_drivers.py`.

See [the authoring guide](../../docs/architecture/execution-plugin-authoring.md)
for Host contracts and installation into a local backend or a Docker image.
