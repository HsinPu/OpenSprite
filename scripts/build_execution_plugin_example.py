"""Build the deterministic, source-only workbench author-example download.

This is repository maintenance automation. No application commands or runtime
plugin installation are exposed. Run from any directory with this script.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import zipfile


SOURCES = (
    "examples/execution-plugin/README.md",
    "examples/execution-plugin/pyproject.toml",
    "examples/execution-plugin/src/opensprite_execution_example/__init__.py",
    "examples/execution-plugin/src/opensprite_execution_example/plugin.py",
    "examples/execution-plugin/tests/test_plugin.py",
    "contracts/agent-loop-v5.sdk.json",
    "docs/architecture/agent-execution-plugins.md",
    "docs/architecture/execution-plugin-authoring.md",
    "scripts/verify_execution_plugin_wheel.py",
)


def build_example_archive(root: Path) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative in sorted(SOURCES):
            # Universal newline decoding produces LF on Windows and Linux,
            # matching Git's canonical text without embedding host metadata.
            source = (root / relative).read_text(encoding="utf-8").encode("utf-8")
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source)
    return output.getvalue()


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    destination = root / "frontend" / "public" / "execution-plugin-example.zip"
    data = build_example_archive(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print(json.dumps({"archive": destination.relative_to(root).as_posix(),
                      "entryCount": len(SOURCES), "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
