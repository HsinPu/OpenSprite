"""A fresh interpreter must execute the core even when product imports fail."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ISOLATED_CHECK = r'''
import sys
from pathlib import Path
import asyncio
import importlib.abc
import importlib.util
import json

blocked = ('fastapi', 'pydantic', 'uvicorn', 'httpx', 'cryptography', 'argon2', 'dbus_next',
    'opensprite_standard_loop', 'opensprite_backend.api', 'opensprite_backend.app',
    'opensprite_backend.runtime', 'opensprite_backend.installed_runtime',
    'opensprite_backend.authentication', 'opensprite_backend.credentials',
    'opensprite_backend.application', 'opensprite_backend.execution_plugins',
    'opensprite_backend.system_prompt', 'opensprite_backend.prompt_logging',
    'opensprite_backend.models', 'opensprite_backend.ai_settings', 'opensprite_backend.general_settings',
    'opensprite_backend.provider_connections', 'opensprite_backend.provider_runtime',
    'opensprite_backend.workspaces.service', 'opensprite_backend.workspaces.store',
    'opensprite_backend.workspaces.policy', 'opensprite_backend.providers.adapters',
    'opensprite_backend.inference.native_gateway')
class BlockProduct(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Product dependency reached by core: ' + fullname)
sys.meta_path.insert(0, BlockProduct())
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'backend/src'))
spec = importlib.util.spec_from_file_location('core_isolation_fixture', root / 'scripts/core_isolation_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
result = asyncio.run(fixture.exercise_core(Path(sys.argv[2])))
assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules for prefix in blocked)
print(json.dumps(result))
'''


def test_core_executes_without_product_or_official_loop_imports(tmp_path):
    completed = subprocess.run([sys.executable, '-I', '-c', ISOLATED_CHECK, str(ROOT), str(tmp_path)],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result['status'] == 'completed' and result['sqliteReloadVerified']
    assert result['pluginId'] == 'isolated_test' and result['modelRequests'] == 1
