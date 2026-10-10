"""Verify normal wheel installation in a venv without product dependencies.

Repository verification only. Supply OPENSPRITE_CORE_WHEEL and
OPENSPRITE_PLUGIN_WHEEL; OPENSPRITE_TEST_UV may select a bundled uv executable.
"""
from importlib import metadata
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    wheel = Path(os.environ['OPENSPRITE_CORE_WHEEL']).resolve()
    example = Path(os.environ['OPENSPRITE_PLUGIN_WHEEL']).resolve()
    uv = os.environ.get('OPENSPRITE_TEST_UV') or shutil.which('uv')
    assert uv and wheel.is_file() and example.is_file()
    output = Path(tempfile.mkdtemp(prefix='core-install-proof-', dir=ROOT / 'tmp'))
    environment = output / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(environment)], check=True, timeout=60)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    def install(path):
        # Normal dependency resolution, no --no-deps: accidental base requirements
        # cannot hide behind an offline test that silently skips dependencies.
        subprocess.run([uv, 'pip', 'install', '--python', str(python), '--no-index', str(path)], check=True, timeout=60)
    check = runpy.run_path(str(ROOT / 'backend/tests/test_core_isolation.py'))['ISOLATED_CHECK']
    check = check.replace("sys.path.insert(0, str(root / 'backend/src'))", "")
    check = check.replace('result = asyncio.run(fixture.exercise_core(Path(sys.argv[2])))', r'''
from importlib import metadata
import opensprite_backend.agent.plugin as sdk
assert Path(sdk.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
installed = {dist.metadata['Name'] for dist in metadata.distributions()}
expected = {'opensprite-backend'} if sys.argv[3] == 'core' else {'opensprite-backend', 'opensprite-execution-example'}
assert installed == expected, installed
assert 'opensprite-standard-loop' not in installed
if sys.argv[3] == 'core':
    result = asyncio.run(fixture.exercise_core(Path(sys.argv[2])))
else:
    from hashlib import sha256
    points = tuple(metadata.entry_points(group='opensprite_backend.agent_loops.v5', name='example_review'))
    assert len(points) == 1
    factory = points[0].load()()
    result = asyncio.run(fixture.exercise_core(Path(sys.argv[2]), factory=factory,
        plugin_id='example_review', plugin_version=metadata.version('opensprite-execution-example')))
result['installed'] = sorted(installed)
result['backendVersion'] = metadata.version('opensprite-backend')
import runpy
golden = runpy.run_path(str(root / 'backend/tests/sdk_v5_contract_support.py'))['contract']()
assert golden == json.loads((root / 'contracts/agent-loop-v5.sdk.json').read_text())
result['sdkV5GoldenMatched'] = True
''')
    def verify(kind):
        completed = subprocess.run([str(python), '-I', '-c', check, str(ROOT), str(output / kind), kind],
            text=True, capture_output=True, timeout=45)
        if completed.returncode:
            print(completed.stderr, file=sys.stderr)
            raise RuntimeError('Installed-core verification failed: ' + kind)
        return json.loads(completed.stdout)
    install(wheel)
    core = verify('core')
    install(example)
    external = verify('example')
    version = tomllib.loads((ROOT / 'backend/pyproject.toml').read_text())['project']['version']
    assert core['backendVersion'] == external['backendVersion'] == version
    from hashlib import sha256
    result = {'core': core, 'externalV5Wheel': external, 'backendWheelSha256': sha256(wheel.read_bytes()).hexdigest(),
              'exampleWheelSha256': sha256(example.read_bytes()).hexdigest(), 'normalOfflineInstallation': True}
    (output / 'evidence.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'evidence': str(output / 'evidence.json'), **result}))


if __name__ == '__main__':
    main()
