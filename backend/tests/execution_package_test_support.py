"""Independent wheel and installed-file fixtures; no plugin is imported."""

from base64 import urlsafe_b64encode
import csv
from hashlib import sha256
from importlib.metadata import EntryPoint, PackageNotFoundError
from io import BytesIO, StringIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_DEFLATED

FILE_NAME = "opensprite_stage2_fixture-0.1.0-py3-none-any.whl"
INFO = "opensprite_stage2_fixture-0.1.0.dist-info"
MODULE = "stage2_fixture_plugin"
GROUP = "opensprite_backend.agent_loops.v2"


def wheel(*, changes=None, removed=(), requirements=(), requires_python=">=3.12,<3.14", metadata_name="opensprite-stage2-fixture"):
    files = {
        MODULE + "/__init__.py": b'raise RuntimeError("IMPORT MUST NOT RUN")\n',
        INFO + "/METADATA": (
            f"Metadata-Version: 2.4\nName: {metadata_name}\nVersion: 0.1.0\n"
            + (f"Requires-Python: {requires_python}\n" if requires_python else "")
            + "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements) + "\n"
        ).encode(),
        INFO + "/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n",
        INFO + "/entry_points.txt": f"[{GROUP}]\nfixture_loop = {MODULE}:factory\n".encode(),
    }
    files.update(changes or {})
    record = StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, content in files.items():
        digest = urlsafe_b64encode(sha256(content).digest()).decode().rstrip("=")
        writer.writerow((name, "sha256=" + digest, str(len(content))))
    writer.writerow((INFO + "/RECORD", "", ""))
    files[INFO + "/RECORD"] = record.getvalue().encode()
    for name in removed:
        files.pop(name, None)
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def paths(tmp_path):
    home = tmp_path / ".opensprite"
    return SimpleNamespace(home=home, execution_plugin_packages_dir=home / "cache" / "execution-plugin-packages")


class InstalledDistribution:
    def __init__(self, root: Path, inspection):
        self.root = root
        self.metadata = {"Name": inspection.distributionName}
        self.version = inspection.version
        self.files = [item.path for item in inspection.files] + [INFO + "/RECORD"]
        self.entry_points = [EntryPoint(name="fixture_loop", value=MODULE + ":factory", group=GROUP)]

    def locate_file(self, path):
        return self.root / str(path)


def absent_distribution(name):
    raise PackageNotFoundError(name)
