"""Read a bounded ZIP in memory; never extract archive paths to disk."""
from io import BytesIO
import stat
import zlib
from zipfile import BadZipFile, ZipFile, ZIP_STORED, ZIP_DEFLATED

from .folder_import import (FolderImportError, PackageFile, MAX_FILES, MAX_FILE_BYTES,
                            MAX_TOTAL_BYTES, FORBIDDEN_DIRECTORIES, safe_segment, validate_paths)

MAX_ZIP_BYTES = 12 * 1024 * 1024


def read_zip(data: bytes) -> tuple[PackageFile, ...]:
    if len(data) > MAX_ZIP_BYTES:
        raise FolderImportError("package_too_large")
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES * 9:
                raise FolderImportError("file_count_exceeded")
            seen = set()
            nodes: dict[str, tuple[str, bool]] = {}
            files = []
            for entry in entries:
                name = entry.orig_filename
                if name != entry.filename or "\\" in name:
                    raise FolderImportError("unsafe_path")
                parts = (name[:-1] if entry.is_dir() else name).split("/")
                if len(parts) > 9:
                    raise FolderImportError("directory_depth_exceeded")
                for part in parts:
                    if safe_segment(part) != part:
                        raise FolderImportError("noncanonical_path")
                    if part.casefold() in FORBIDDEN_DIRECTORIES:
                        raise FolderImportError("excluded_directory")
                for index in range(1, len(parts) + 1):
                    prefix = "/".join(parts[:index])
                    is_file = index == len(parts) and not entry.is_dir()
                    previous = nodes.get(prefix.casefold())
                    if previous and (previous[0] != prefix or previous[1] or is_file):
                        raise FolderImportError("duplicate_path")
                    nodes[prefix.casefold()] = (prefix, is_file)
                key = name.rstrip("/").casefold()
                if key in seen:
                    raise FolderImportError("duplicate_path")
                seen.add(key)
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or bool(entry.external_attr & 0x400):
                    raise FolderImportError("unsafe_path")
                if entry.flag_bits & 1:
                    raise FolderImportError("encrypted_zip")
                if entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
                    raise FolderImportError("unsupported_zip")
                if entry.is_dir():
                    if entry.file_size:
                        raise FolderImportError("invalid_zip")
                else:
                    if mode == stat.S_IFDIR:
                        raise FolderImportError("unsafe_path")
                    files.append(entry)
            if not 1 <= len(files) <= MAX_FILES:
                raise FolderImportError("file_count_exceeded")
            names = [entry.filename for entry in files]
            # Exactly one optional wrapper directory, not a multi-Skill archive.
            wrapper = "" if "SKILL.md" in names else names[0].split("/")[0] + "/"
            if wrapper and (not all(name.startswith(wrapper) for name in names) or wrapper + "SKILL.md" not in names):
                raise FolderImportError("missing_entrypoint")
            paths = validate_paths([name[len(wrapper):] for name in names])
            total = 0
            result = []
            for entry, path in zip(files, paths, strict=True):
                limit = 65536 if path == "SKILL.md" else MAX_FILE_BYTES
                if entry.file_size > limit:
                    raise FolderImportError("content_too_large", path)
                total += entry.file_size
                if total > MAX_TOTAL_BYTES:
                    raise FolderImportError("package_too_large")
                with archive.open(entry) as source:
                    content = source.read(limit + 1)
                if len(content) != entry.file_size or len(content) > limit:
                    raise FolderImportError("invalid_zip")
                result.append(PackageFile(path, content))
            return tuple(result)
    except (BadZipFile, ValueError, EOFError, OSError, NotImplementedError, RuntimeError, zlib.error):
        raise FolderImportError("invalid_zip") from None
