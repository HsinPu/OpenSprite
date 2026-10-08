# OpenSprite execution example 0.2.0

This pure-Python package targets OpenSprite >=0.21.31,<0.22 and Host API v2.
`example_checkpointed` is an independent driver that checks cancellation around a text model turn and returns the exact Host result.
`example_main_retry_only` permits eligible main-provider context retry and vetoes automatic output continuation.
Both factories return fresh per-task instances. There is no persistence, credential access or direct Provider connection in this example.

## Build and test

From the OpenSprite repository root:

```bash
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml examples/execution-plugin/tests
uv build --wheel --out-dir tmp/execution-plugin-wheel examples/execution-plugin
```

PowerShell installed-wheel verification:

```powershell
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path tmp/execution-plugin-wheel/opensprite_execution_example-0.2.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

For the downloaded ZIP, run the same commands from its root: it contains `examples/`, `docs/` and `scripts/`; a compatible backend environment is required.
Source-only unit tests verify coordination. The wheel verifier installs into a temporary target and exercises the installed implementation through a real AgentLoop/SQLite/native adapter with variable protocol-fixture output.
This does not prove a paid Provider or arbitrary task outcome.

## Install

Import the reviewed wheel in Settings → Execution, download its deployment bundle, follow the bundle README to build/restart the existing Docker project, refresh deployment status, then apply the discovered Loop/policy to future tasks.
Import only stores and statically checks a package. It neither runs code nor modifies the running Python environment.
For desktop installation, stop the backend and install into its actual Python environment before restarting.
Keep the existing user-data root and one writer. API v1 wheels are incompatible and must be rewritten for text Host v2.

See [authoring](../../docs/architecture/execution-plugin-authoring.md) and [execution architecture](../../docs/architecture/agent-execution-plugins.md).
