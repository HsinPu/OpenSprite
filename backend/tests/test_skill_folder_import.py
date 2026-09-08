"""Skill package structure and resource bounds, independent of source OS."""
import pytest
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED


def archive_bytes(entries):
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path, data in entries:
            archive.writestr(path, data)
    return output.getvalue()


def zip_parts(manifest, entries):
    import json
    return [("manifest", (None, json.dumps({key: value for key, value in manifest.items() if key != "files"}))),
            ("archive", ("skill.zip", archive_bytes(entries)))]


from opensprite_backend.skills.folder_import import (
    FolderImportError, PackageFile, validate_package, validate_paths,
)
from test_skills import CONTENT, setup, WORKSPACE_ID


def package(*extra):
    return (PackageFile("SKILL.md", CONTENT.encode()), *extra)


def test_long_zip_with_200_valid_paths_is_accepted():
    from opensprite_backend.skills.zip_import import read_zip
    prefix = "/".join(chr(97 + i) * 50 for i in range(6))
    paths = ["SKILL.md"] + [prefix + "/" + "x" * 46 + str(i) + ".txt" for i in range(199)]
    data = archive_bytes([(path, CONTENT.encode() if i == 0 else b"x") for i, path in enumerate(paths)])
    assert len(validate_package("review", read_zip(data)).files) == 200


def test_duplicate_manifest_keys_are_invalid_request(tmp_path):
    from test_skill_routes import client_for
    with client_for(tmp_path) as client:
        raw = '{"scope":"global","scope":"global"}'
        response = client.post("/api/skills/import-zip", files={"manifest": (None, raw)})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"
        assert response.json()["error"]["retryable"] is False


def test_bom_import_preserves_bytes_hash_and_can_be_enabled(tmp_path):
    import hashlib
    import json
    from test_skill_routes import client_for
    data = b"\xef\xbb\xbf" + CONTENT.encode()
    manifest = {"scope": "global", "workspaceId": None, "directoryName": "review", "expectedRevision": 0,
                "files": [{"id": "file-0", "path": "SKILL.md"}]}
    with client_for(tmp_path) as client:
        response = client.post("/api/skills/import-zip", files=zip_parts(manifest, [("SKILL.md", data)]))
        assert response.status_code == 200, response.text
        item = response.json()["skill"]
        assert item["contentHash"] == hashlib.sha256(data).hexdigest()
        assert item["content"].encode() == data
        assert item["enabled"] is True
        assert client.put(f'/api/skills/{item["id"]}/enabled', json={"enabled": True, "expectedRevision": 1}).status_code == 200
        assert client.get("/api/skills?scope=global").json()["skills"][0]["effective"] is True


def test_oversized_manifest_remains_rejected(tmp_path):
    from test_skill_routes import client_for
    from opensprite_backend.api.skill_zip_upload import MAX_MANIFEST_BYTES
    with client_for(tmp_path) as client:
        response = client.post("/api/skills/import-zip", files={"manifest": (None, " " * (MAX_MANIFEST_BYTES + 1))})
        assert response.status_code == 400


def test_package_keeps_display_and_directory_names_separate():
    result = validate_package("code-review", package(PackageFile("scripts/check.py", b"raise RuntimeError")))
    assert result.name == "review"
    assert result.directory_name == "code-review"
    assert len(result.manifest_hash) == 64
    assert result.files[1].data == b"raise RuntimeError"
    assert "raise RuntimeError" not in repr(result)


@pytest.mark.parametrize("path", [
    "../escape", "/absolute", "C:/root", "a\\b", "a//b", "a/./b", "NUL.txt",
    "file.", "a/node_modules/file.js", ".git/config", "nested/SKILL.md", "skill.md",
    "a/" * 8 + "b", "e\u0301.txt",
])
def test_unsafe_or_wrong_structure(path):
    with pytest.raises(FolderImportError):
        validate_package("example", package(PackageFile(path, b"data")))


@pytest.mark.parametrize("paths", [
    ["a", "a/b"], ["a/b", "a"], ["A/b", "a/c"], ["x", "X"], ["x", "x"],
])
def test_collisions(paths):
    with pytest.raises(FolderImportError, match="duplicate_path"):
        validate_paths(["SKILL.md", *paths])


def test_entrypoint_and_limits():
    with pytest.raises(FolderImportError, match="missing_entrypoint"):
        validate_paths(["README.md"])
    with pytest.raises(FolderImportError, match="file_count_exceeded"):
        validate_paths(["SKILL.md", *[f"f{i}" for i in range(200)]])
    with pytest.raises(FolderImportError, match="content_too_large"):
        validate_package("example", package(PackageFile("large", b"x" * (5 * 1024 * 1024 + 1))))
    with pytest.raises(FolderImportError, match="package_too_large"):
        validate_package("example", package(*[PackageFile(f"f{i}", b"x" * (5 * 1024 * 1024)) for i in range(2)]))
    with pytest.raises(FolderImportError, match="invalid_format"):
        validate_package("example", (PackageFile("SKILL.md", b"\xff"),))


def test_common_directories_are_valid_and_hash_is_order_independent():
    files = package(PackageFile("references/a.md", b"text"), PackageFile("assets/a.bin", b"\x00"))
    assert validate_package("example", files).manifest_hash == validate_package("example", tuple(reversed(files))).manifest_hash


def test_portable_path_segments_respect_ext4_utf8_byte_limit():
    accepted = "\U0001f600" * 63
    rejected = "\U0001f600" * 64

    assert validate_paths(["SKILL.md", accepted]) == ("SKILL.md", accepted)
    with pytest.raises(FolderImportError, match="unsafe_path"):
        validate_paths(["SKILL.md", rejected])


@pytest.mark.parametrize("scope", ["global", "workspace"])
def test_import_starts_enabled_and_archives_whole_folder(tmp_path, scope):
    service = setup(tmp_path)
    workspace_id = WORKSPACE_ID if scope == "workspace" else None
    files = package(PackageFile("scripts/check.py", b"raise RuntimeError('never execute')"))
    result = service.import_folder(scope=scope, workspace_id=workspace_id, directory_name="code-review", files=files, expected=0)
    item = result["skill"]
    assert item["name"] == "review" and item["directoryName"] == "code-review"
    assert item["enabled"] and service.snapshot(WORKSPACE_ID).available
    path = service._base(scope, workspace_id) / "code-review"
    assert path.joinpath("scripts/check.py").read_bytes() == files[1].data
    with pytest.raises(Exception, match="revision_conflict"):
        service.import_folder(scope=scope, workspace_id=workspace_id, directory_name="code-review", files=files, expected=0)
    assert len(service.list(scope, workspace_id)["skills"]) == 1
    service.delete(item["id"], 1)
    assert next(service.paths.skills_archive_dir.glob("*/scripts/check.py")).read_bytes() == files[1].data


def test_import_recovery_after_rename_before_catalog(tmp_path, monkeypatch):
    service = setup(tmp_path)
    import opensprite_backend.atomic_file as atomic
    original = atomic.atomic_write
    def fail(path, data):
        if path == service.paths.skills_settings_file:
            raise OSError("injected")
        original(path, data)
    monkeypatch.setattr(atomic, "atomic_write", fail)
    with pytest.raises(Exception, match="store_unavailable"):
        service.import_folder(scope="global", workspace_id=None, directory_name="example", files=package(), expected=0)
    assert service.paths.skills_dir.joinpath("example/SKILL.md").exists()
    monkeypatch.setattr(atomic, "atomic_write", original)
    assert service.list("global")["skills"][0]["directoryName"] == "example"
    assert not service.paths.skills_transaction_file.exists()


def test_existing_directory_is_never_overwritten(tmp_path):
    service = setup(tmp_path)
    target = service.paths.skills_dir / "EXAMPLE"
    target.mkdir(parents=True)
    target.joinpath("keep").write_bytes(b"keep")
    with pytest.raises(Exception, match="directory_exists"):
        service.import_folder(scope="global", workspace_id=None, directory_name="example", files=package(), expected=0)
    assert target.joinpath("keep").read_bytes() == b"keep"


def test_multipart_import_and_strict_file_mapping(tmp_path):
    import json
    from test_skill_routes import client_for
    manifest = {"scope": "global", "workspaceId": None, "directoryName": "example", "expectedRevision": 0,
                "files": [{"id": "file-0", "path": "SKILL.md"}, {"id": "file-1", "path": "assets/a.bin"}]}
    with client_for(tmp_path) as client:
        files = zip_parts(manifest, [("SKILL.md", CONTENT.encode()), ("assets/a.bin", b"\x00")])
        response = client.post("/api/skills/import-zip", files=files)
        assert response.status_code == 200, response.text
        assert response.json()["skill"]["enabled"]
        assert client.post("/api/skills/import-zip", files=files).status_code == 409
        assert client.post("/api/skills/import-zip", files=files + [("file-1", ("duplicate", b"x"))]).status_code == 400
        assert client.post("/api/skills/import-zip", files=files[:-1]).status_code == 400
        manifest["unexpected"] = True
        files[0] = ("manifest", (None, json.dumps(manifest)))
        assert client.post("/api/skills/import-zip", files=files).status_code == 400


def test_folder_route_is_authenticated(tmp_path):
    from test_authentication import authentication
    from fastapi.testclient import TestClient
    from opensprite_backend.app import create_app
    auth, _ = authentication(tmp_path)
    with TestClient(create_app(local_authentication=auth, enforce_authentication=True)) as client:
        assert client.post("/api/skills/import-zip", content=b"unparsed").status_code == 401


def test_oversized_part_is_rejected_without_disk_registration(tmp_path):
    from test_skill_routes import client_for
    with client_for(tmp_path) as client:
        response = client.post("/api/skills/import-zip", files={"archive": ("ignored", b"x" * (12 * 1024 * 1024 + 1))})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "file_too_large"
        assert client.get("/api/skills?scope=global").json()["skills"] == []


def test_failed_stage_write_is_archived_without_blocking_catalog(tmp_path, monkeypatch):
    service = setup(tmp_path)
    prior = service.save(scope="global", workspace_id=None, content=CONTENT.replace("name: review", "name: existing"), expected=0)
    import opensprite_backend.atomic_file as atomic
    original = atomic.atomic_write
    def fail(path, data):
        if path.name == "second.txt":
            raise OSError("injected")
        original(path, data)
    monkeypatch.setattr(atomic, "atomic_write", fail)
    with pytest.raises(Exception, match="store_unavailable"):
        service.import_folder(scope="global", workspace_id=None, directory_name="example", files=package(PackageFile("transaction.json", b"user data"), PackageFile("second.txt", b"test")), expected=1)
    assert not service.paths.skills_dir.joinpath("example").exists()
    assert [item["id"] for item in service.list("global")["skills"]] == [prior["skill"]["id"]]
    assert not service.paths.skills_transaction_file.exists()
    archives = list(service.paths.skills_archive_dir.glob("failed-import-*"))
    assert len(archives) == 1
    assert (archives[0] / "transaction.json").is_file()
    assert (archives[0] / "payload" / "SKILL.md").read_bytes() == CONTENT.encode()
    assert (archives[0] / "payload" / "transaction.json").read_bytes() == b"user data"
    monkeypatch.setattr(atomic, "atomic_write", original)
    service.import_folder(scope="global", workspace_id=None, directory_name="example", files=package(PackageFile("second.txt", b"test")), expected=1)
    assert len(service.list("global")["skills"]) == 2
    assert service.paths.skills_dir.joinpath("example/second.txt").read_bytes() == b"test"


@pytest.mark.parametrize("interrupt_catalog", [False, True])
def test_actual_long_path_import_read_and_archive(tmp_path, monkeypatch, interrupt_catalog):
    import json
    import shutil
    from test_skill_routes import client_for
    from opensprite_backend.skills.folder_import import disk_path
    # Keep pytest cleanup from encountering non-extended Windows paths.
    root = tmp_path / "long-import"
    root.mkdir()
    prefix = "/".join(chr(97 + i) * 50 for i in range(6))
    paths = ["SKILL.md"] + [prefix + "/" + "x" * 46 + str(i) + ".txt" for i in range(199)]
    manifest = {"scope": "global", "workspaceId": None, "directoryName": "review", "expectedRevision": 0,
                "files": [{"id": f"file-{i}", "path": path} for i, path in enumerate(paths)]}
    try:
        with client_for(root) as client:
            service = client.app.state.skills
            import opensprite_backend.atomic_file as atomic
            original = atomic.atomic_write
            def fail_catalog(path, data):
                if path == service.paths.skills_settings_file:
                    raise OSError("injected after long-path publication")
                original(path, data)
            if interrupt_catalog:
                monkeypatch.setattr(atomic, "atomic_write", fail_catalog)
            response = client.post("/api/skills/import-zip", files=zip_parts(manifest, [(path, CONTENT.encode() if i == 0 else b"x") for i, path in enumerate(paths)]))
            assert response.status_code == (503 if interrupt_catalog else 200), response.text
            monkeypatch.setattr(atomic, "atomic_write", original)
            if interrupt_catalog:
                from opensprite_backend.skills.service import SkillsService
                client.app.state.skills = SkillsService(service.paths, service.workspaces)
            assert client.get("/api/skills?scope=global").status_code == 200
            destination = disk_path(service.paths.skills_dir / "review")
            assert destination.joinpath(*paths[-1].split("/")).read_bytes() == b"x"
            identifier = client.get("/api/skills?scope=global").json()["skills"][0]["id"]
            assert client.delete(f"/api/skills/{identifier}?expectedRevision=1").status_code == 200
            assert client.get("/api/skills?scope=global").json()["skills"] == []
    finally:
        if root.exists():
            shutil.rmtree(disk_path(root))


def test_recovery_never_overwrites_unexpected_destination(tmp_path, monkeypatch):
    service = setup(tmp_path)
    import opensprite_backend.atomic_file as atomic
    original = atomic.atomic_write
    def fail(path, data):
        if path == service.paths.skills_settings_file:
            raise OSError("injected")
        original(path, data)
    monkeypatch.setattr(atomic, "atomic_write", fail)
    with pytest.raises(Exception):
        service.import_folder(scope="global", workspace_id=None, directory_name="example", files=package(), expected=0)
    target = service.paths.skills_dir / "example" / "SKILL.md"
    target.write_bytes(b"other content")
    monkeypatch.setattr(atomic, "atomic_write", original)
    with pytest.raises(Exception, match="store_unavailable"):
        service.list("global")
    assert target.read_bytes() == b"other content"


def test_disconnect_closes_in_memory_uploads(monkeypatch):
    import asyncio
    from starlette.requests import ClientDisconnect, Request
    from opensprite_backend.api import skill_zip_upload as upload
    seen = []
    original = upload.BoundedParser

    class TrackingParser(original):
        def on_headers_finished(self):
            super().on_headers_finished()
            seen.extend(self._files_to_close_on_error)

    monkeypatch.setattr(upload, "BoundedParser", TrackingParser)
    messages = iter([
        {"type": "http.request", "body": b'--test\r\nContent-Disposition: form-data; name="file-0"; filename="file"\r\n\r\npartial', "more_body": True},
        {"type": "http.disconnect"},
    ])
    async def receive():
        return next(messages)
    request = Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=test")]}, receive)
    with pytest.raises(ClientDisconnect):
        asyncio.run(upload.read_zip_upload(request))
    assert seen and all(file.closed for file in seen)
