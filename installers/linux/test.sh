#!/usr/bin/env bash
set -euo pipefail
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/opensprite-installer-test-XXXXXX")"; trap 'rm -rf -- "$ROOT"' EXIT
python3 - "$ROOT" "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)" <<'PY'
import importlib.util, io, json, pathlib, sys
root=pathlib.Path(sys.argv[1])/".opensprite"; source=pathlib.Path(sys.argv[2])
sys.path.insert(0, str(source/"backend/src"))
spec=importlib.util.spec_from_file_location("linux_access", source/"installers/linux/access.py")
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
from opensprite_backend.authentication import AccessMode
module.set_access_mode(root, AccessMode.TRUSTED_LOCAL)
assert json.loads((root/"config/access-policy.json").read_text())["mode"] == "trusted_local"
tty=io.StringIO(); assert module.issue_bootstrap(root, 8765, False, tty)
url=tty.getvalue(); stored=(root/"state/access-bootstrap.json").read_text()
assert "#setup=" in url and url.split("#setup=",1)[1].strip() not in stored
(root/"data").mkdir(); (root/"data/opensprite.db").write_text("keep")
tty=io.StringIO(); assert module.issue_bootstrap(root, 8765, True, tty)
assert (root/"data/opensprite.db").read_text() == "keep"
PY
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/install.sh" --source-root "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)" --test-root "$ROOT" --access-mode trusted_local
[[ -f "$ROOT/app/frontend/dist/index.html" ]]
[[ -f "$ROOT/app/backend/.venv/bin/uvicorn" ]]
[[ "$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["mode"])' "$ROOT/.opensprite/config/access-policy.json")" == "trusted_local" ]]
echo "Linux installer helper test passed."
