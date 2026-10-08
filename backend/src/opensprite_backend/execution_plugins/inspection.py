"""Bounded metadata-only wheel inspection; archive members are never imported."""

from base64 import urlsafe_b64encode
import configparser
import csv
from email import policy
from email.parser import BytesParser
from hashlib import sha256
from importlib import metadata
from io import BytesIO, StringIO
import re
import stat
import sys
import zlib
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED, ZIP_STORED

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import parse_tag, sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from .models import (ExecutionPackageError, MAX_FILES, MAX_FILE_BYTES, MAX_UNPACKED_BYTES,
                     MAX_WHEEL_BYTES, PackageFile, PackagePlugin, WheelInspection)

_GROUP = re.compile(r"^opensprite_backend\.(agent_loops|execution_policies)\.v([1-9][0-9]*)$")
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_ENTRY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}$")
_NATIVE = {".so", ".pyd", ".dll", ".dylib", ".exe", ".pyc", ".pth", ".sh", ".ps1", ".bat", ".cmd"}
_RESERVED = {"opensprite_backend", "sitecustomize", "usercustomize"}


def _invalid():
    raise ExecutionPackageError("invalid_package")


def safe_member(name: str) -> str:
    if not isinstance(name, str) or len(name) > 256 or "\\" in name or name.endswith("/"):
        _invalid()
    parts = name.split("/")
    if len(parts) > 12 or any(part in {".", ".."} or not _SEGMENT.fullmatch(part) for part in parts):
        _invalid()
    if any(part.endswith((".", " ")) or part.split(".")[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
    } for part in parts):
        _invalid()
    return name


def _headers(data: bytes):
    if len(data) > 256 * 1024:
        _invalid()
    data.decode("utf-8", errors="strict")
    result = BytesParser(policy=policy.default).parsebytes(data)
    if result.defects:
        _invalid()
    return result


def _one(headers, name: str, *, optional=False):
    values = headers.get_all(name, [])
    if optional and not values:
        return None
    if len(values) != 1 or not str(values[0]).strip():
        _invalid()
    return str(values[0]).strip()


def check_environment(requires_python, requirements, *, versions=None, environment=None):
    env = default_environment() if environment is None else dict(environment)
    if requires_python is not None and not SpecifierSet(requires_python).contains(env["python_full_version"], prereleases=True):
        raise ExecutionPackageError("incompatible_package")
    for raw in requirements:
        requirement = Requirement(raw)
        if requirement.url is not None or requirement.extras:
            _invalid()
        if requirement.marker is not None and not requirement.marker.evaluate(env):
            continue
        try:
            installed = metadata.version(requirement.name) if versions is None else versions[canonicalize_name(requirement.name)]
        except (metadata.PackageNotFoundError, KeyError):
            raise ExecutionPackageError("incompatible_package") from None
        if not requirement.specifier.contains(installed, prereleases=True):
            raise ExecutionPackageError("incompatible_package")


def inspect_wheel(data: bytes, file_name: str, *, validate_environment=True,
                  versions=None, environment=None, owners=None,
                  allow_retired_api=False) -> WheelInspection:
    if len(data) > MAX_WHEEL_BYTES:
        raise ExecutionPackageError("package_too_large")
    try:
        safe_member(file_name)
        if "/" in file_name or not file_name.endswith(".whl"):
            _invalid()
        wheel_name, wheel_version, _, wheel_tags = parse_wheel_filename(file_name)
        if any(tag.abi != "none" or tag.platform != "any" for tag in wheel_tags):
            _invalid()
        if not set(wheel_tags).intersection(sys_tags()):
            raise ExecutionPackageError("incompatible_package")
        contents = {}
        folded = set()
        nodes = {}
        total = 0
        with ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            if not 1 <= len(members) <= MAX_FILES:
                _invalid()
            for member in members:
                name = member.orig_filename
                if name != member.filename:
                    _invalid()
                is_directory = member.is_dir()
                path = safe_member(name[:-1] if is_directory else name)
                folded_path = path.casefold()
                if folded_path in folded:
                    _invalid()
                folded.add(folded_path)
                segments = path.split("/")
                for index in range(1, len(segments) + 1):
                    prefix = "/".join(segments[:index])
                    leaf_file = index == len(segments) and not is_directory
                    previous = nodes.get(prefix.casefold())
                    if previous and (previous[0] != prefix or previous[1] or leaf_file):
                        _invalid()
                    nodes[prefix.casefold()] = (prefix, leaf_file)
                mode = stat.S_IFMT(member.external_attr >> 16)
                if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or member.external_attr & 0x400 or member.flag_bits & 1:
                    _invalid()
                if member.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
                    _invalid()
                if is_directory:
                    if member.file_size:
                        _invalid()
                    continue
                if mode == stat.S_IFDIR or member.file_size > MAX_FILE_BYTES:
                    _invalid()
                total += member.file_size
                if total > MAX_UNPACKED_BYTES:
                    raise ExecutionPackageError("package_too_large")
                if any(part.endswith(".data") for part in segments) or any(
                    part.casefold().split(".")[0] in _RESERVED for part in segments
                ) or any(path.casefold().endswith(extension) for extension in _NATIVE):
                    _invalid()
                with archive.open(member) as stream:
                    content = stream.read(MAX_FILE_BYTES + 1)
                if len(content) != member.file_size or len(content) > MAX_FILE_BYTES:
                    _invalid()
                contents[path] = content
        roots = {path.split("/")[0] for path in contents}
        metadata_roots = [root for root in roots if root.endswith(".dist-info")]
        if len(metadata_roots) != 1:
            _invalid()
        info = metadata_roots[0]
        required = [f"{info}/{name}" for name in ("METADATA", "WHEEL", "RECORD", "entry_points.txt")]
        if any(path not in contents for path in required):
            _invalid()
        headers = _headers(contents[required[0]])
        if not re.fullmatch(r"2\.[0-9]+", _one(headers, "Metadata-Version")):
            _invalid()
        name = _one(headers, "Name")
        version = _one(headers, "Version")
        normalized = canonicalize_name(name, validate=True)
        if normalized == "opensprite-backend" or len(name) > 128 or len(version) > 64:
            _invalid()
        if wheel_name != normalized or wheel_version != Version(version):
            _invalid()
        expected_info = normalized.replace("-", "_") + "-" + str(wheel_version) + ".dist-info"
        if info != expected_info:
            _invalid()
        wheel_headers = _headers(contents[required[1]])
        if _one(wheel_headers, "Wheel-Version") != "1.0" or _one(wheel_headers, "Root-Is-Purelib") != "true":
            _invalid()
        declared_tags = set()
        for raw in wheel_headers.get_all("Tag", []):
            declared_tags.update(parse_tag(str(raw)))
        if declared_tags != set(wheel_tags):
            _invalid()
        requirements = [str(item).strip() for item in headers.get_all("Requires-Dist", [])]
        requires_python = _one(headers, "Requires-Python", optional=True)
        if len(requirements) > 64 or any(not raw or len(raw) > 512 for raw in requirements) or (
            requires_python is not None and len(requires_python) > 256
        ):
            _invalid()
        # Even excluded requirements cannot name URLs/extras: deployment never resolves them.
        for raw in requirements:
            requirement = Requirement(raw)
            if requirement.url or requirement.extras:
                _invalid()
        if requires_python is not None:
            SpecifierSet(requires_python)
        if validate_environment:
            check_environment(requires_python, requirements, versions=versions, environment=environment)
        if validate_environment:
            try:
                installed_distribution = metadata.distribution(normalized)
            except metadata.PackageNotFoundError:
                installed_distribution = None
            if installed_distribution is not None and not any(_GROUP.fullmatch(point.group)
                for point in installed_distribution.entry_points):
                # A plugin import must never replace an ordinary installed dependency.
                _invalid()
        module_owners = metadata.packages_distributions() if owners is None else owners
        for root in roots - {info}:
            module = root[:-3] if root.endswith(".py") else root
            if "." in module or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module):
                _invalid()
            if module in sys.stdlib_module_names or any(canonicalize_name(owner) != normalized
                for owner in module_owners.get(module, ())):
                _invalid()
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(contents[required[3]].decode("utf-8", errors="strict"))
        if parser.defaults():
            _invalid()
        plugins = []
        for group in parser.sections():
            match = _GROUP.fullmatch(group)
            if match is None:
                _invalid()
            api_version = int(match[2])
            if not (match[1] == "agent_loops" and api_version == 3) and not (allow_retired_api and api_version in {1, 2}):
                raise ExecutionPackageError("incompatible_package")
            kind = "loop" if match[1] == "agent_loops" else "policy"
            for identifier, entry in parser.items(group, raw=True):
                entry = entry.strip()
                if not _ID.fullmatch(identifier) or not _ENTRY.fullmatch(entry) or len(entry) > 256:
                    _invalid()
                if identifier in {"standard", "no_recovery"}:
                    _invalid()
                module = entry.split(":", 1)[0].replace(".", "/")
                if module + ".py" not in contents and module + "/__init__.py" not in contents:
                    _invalid()
                plugins.append(PackagePlugin(id=identifier, kind=kind, apiVersion=api_version, entryPoint=entry))
        if not 1 <= len(plugins) <= 32:
            _invalid()
        if validate_environment:
            installed_points = metadata.entry_points()
            for plugin in plugins:
                group = "opensprite_backend." + ("agent_loops" if plugin.kind == "loop" else "execution_policies") + f".v{plugin.apiVersion}"
                for point in installed_points.select(group=group, name=plugin.id):
                    if point.dist is None or canonicalize_name(point.dist.metadata["Name"]) != normalized:
                        _invalid()
        # RECORD covers every member once, including the unhashed RECORD itself.
        rows = list(csv.reader(StringIO(contents[required[2]].decode("utf-8", errors="strict")), strict=True))
        recorded = set()
        for row in rows:
            if len(row) != 3 or row[0] in recorded or row[0] not in contents:
                _invalid()
            path, digest, size = row
            recorded.add(path)
            if path == required[2]:
                if digest or size:
                    _invalid()
            else:
                expected = "sha256=" + urlsafe_b64encode(sha256(contents[path]).digest()).decode("ascii").rstrip("=")
                if digest != expected or size != str(len(contents[path])):
                    _invalid()
        if recorded != set(contents):
            _invalid()
        return WheelInspection(
            fileName=file_name, distributionName=normalized, version=version,
            sha256=sha256(data).hexdigest(), sizeBytes=len(data), requiresPython=requires_python,
            requiresDist=requirements, plugins=plugins,
            files=[PackageFile(path=path, sha256=sha256(content).hexdigest(), sizeBytes=len(content))
                   for path, content in sorted(contents.items()) if path != required[2]],
        )
    except ExecutionPackageError:
        raise
    except (Exception,):
        raise ExecutionPackageError("invalid_package") from None
