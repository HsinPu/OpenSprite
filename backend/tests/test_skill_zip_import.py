import stat
from io import BytesIO
from zipfile import ZipFile, ZipInfo

import pytest

from opensprite_backend.skills.zip_import import read_zip
from opensprite_backend.skills.models import SkillError
from test_skill_folder_import import archive_bytes
from test_skills import CONTENT


@pytest.mark.parametrize("prefix", ["", "code-review/"])
def test_accepts_one_skill_with_or_without_wrapper(prefix):
    files = read_zip(archive_bytes([(prefix + "SKILL.md", CONTENT.encode()), (prefix + "assets/a.txt", b"hello")]))
    assert [item.path for item in files] == ["SKILL.md", "assets/a.txt"]
    assert files[1].data == b"hello"


@pytest.mark.parametrize("path", ["../escape", "/root", "C:/test", "a\\b", "a/../../b", "CON", "a/skill.md", "a/SKILL.md", "assets/.git/config"])
def test_rejects_unsafe_zip_paths(path):
    data = archive_bytes([("SKILL.md", CONTENT.encode()), (path, b"x")])
    if path == "a\\b":
        # zipfile normalizes separators while writing on Windows.
        data = data.replace(b"a/b", b"a\\b")
    with pytest.raises(SkillError):
        read_zip(data)


def test_rejects_links_and_encrypted_archives():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        entry = ZipInfo("SKILL.md")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, CONTENT.encode())
    with pytest.raises(SkillError, match="unsafe_path"):
        read_zip(output.getvalue())
    data = bytearray(archive_bytes([("SKILL.md", CONTENT.encode())]))
    index = data.index(b"PK\x01\x02")
    data[index + 8] |= 1
    with pytest.raises(SkillError, match="encrypted_zip"):
        read_zip(bytes(data))


def test_rejects_corruption_and_resource_limits():
    for data in [b"not a zip", archive_bytes([("SKILL.md", b"x" * 65537)]),
                 archive_bytes([("SKILL.md", CONTENT.encode()), ("large", b"x" * (5 * 1024 * 1024 + 1))]),
                 archive_bytes([("SKILL.md", CONTENT.encode())] + [(str(i), b"") for i in range(200)])]:
        with pytest.raises(SkillError):
            read_zip(data)


def test_old_folder_endpoint_is_removed(tmp_path):
    from test_skill_routes import client_for
    with client_for(tmp_path) as client:
        assert client.post("/api/skills/import-folder").status_code in (404, 405)


@pytest.mark.parametrize("paths", [
    [".git/SKILL.md"], ["SKILL.md", ".git/"], ["SKILL.md", "../"],
    ["SKILL.md", "assets/", "assets"], ["SKILL.md", "assets", "assets/"],
    ["SKILL.md", "Assets/", "assets/a"], ["SKILL.md", "assets//"],
])
def test_checks_all_archive_nodes_before_discarding_directories(paths):
    data = archive_bytes([(path, b"" if path.endswith("/") else CONTENT.encode()) for path in paths])
    with pytest.raises(SkillError):
        read_zip(data)


@pytest.mark.parametrize("paths", [
    ["review/", "review/assets/", "review/SKILL.md", "review/assets/a"],
    ["review/SKILL.md", "review/assets/a", "review/assets/", "review/"],
])
def test_accepts_explicit_directories_before_or_after_files(paths):
    result = read_zip(archive_bytes([(path, b"" if path.endswith("/") else CONTENT.encode()) for path in paths]))
    assert len(result) == 2
