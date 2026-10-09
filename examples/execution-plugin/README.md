# OpenSprite execution example 0.5.0

Pure Python, OpenSprite >=0.21.35,<0.22, Host API v5. The example_review
Loop performs three actual requests: private draft, private review and published
final answer. Review receives draft text; final receives draft plus critique.
Only final text becomes the conversation answer. Each Run gets a fresh instance.

From the OpenSprite repository root:

```bash
uv sync --project backend --dev
uv run --project backend python -m pytest -c examples/execution-plugin/pyproject.toml examples/execution-plugin/tests
uv build --wheel --out-dir tmp/v5-wheels examples/execution-plugin
```

PowerShell installed-wheel check:

```powershell
$env:OPENSPRITE_PLUGIN_WHEEL = (Resolve-Path tmp/v5-wheels/opensprite_execution_example-0.5.0-py3-none-any.whl).Path
uv run --project backend python scripts/verify_execution_plugin_wheel.py
```

Source tests check decisions. The separate verifier installs the actual wheel
offline in a temporary target and isolated Python process, then tests real Host,
SQLite, native adapter, variable protocol output and cancellation. It is not a
paid Provider test.

The downloaded ZIP includes examples/, docs/ and scripts/. Use a compatible
backend environment. Import in Settings → Execution, build/restart with the
deployment bundle, verify deployment, then apply the installed Loop.
Import alone stores a reviewed package; it does not install or select it.
Keep the current .opensprite and one writer. Review trusted code before installation.
Old API v1/v2/v3/v4 wheels must be rewritten; there is no compatibility wrapper.

See [authoring](../../docs/architecture/execution-plugin-authoring.md)
and [architecture](../../docs/architecture/agent-execution-plugins.md).
