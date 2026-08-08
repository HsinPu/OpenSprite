"""Frontend path resolution for the Web integration runtime."""

from pathlib import Path

from opensprite.integrations.web.runtime import resolve_frontend_dir, resolve_frontend_source_dir


def test_repository_frontend_resolution_does_not_depend_on_module_depth(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    frontend = repository / "frontend"
    distribution = frontend / "dist"
    distribution.mkdir(parents=True)
    package_root = repository / "src" / "opensprite"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (repository / "pyproject.toml").write_text("[project]\nname = 'example'\n", encoding="utf-8")
    (frontend / "package.json").write_text('{"name":"example"}\n', encoding="utf-8")
    (distribution / "index.html").write_text("<html></html>\n", encoding="utf-8")

    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)

    module_paths = (
        repository / "src" / "opensprite" / "channels" / "web.py",
        repository / "src" / "opensprite" / "integrations" / "web" / "adapter.py",
    )
    for module_path in module_paths:
        assert resolve_frontend_source_dir({}, module_path=module_path) == frontend.resolve()
        assert resolve_frontend_dir({}, module_path=module_path) == distribution.resolve()


def test_installed_package_does_not_use_host_project_frontend(tmp_path, monkeypatch):
    host_project = tmp_path / "host"
    host_frontend = host_project / "frontend"
    host_distribution = host_frontend / "dist"
    host_distribution.mkdir(parents=True)
    (host_project / "pyproject.toml").write_text("[project]\nname = 'host'\n", encoding="utf-8")
    (host_frontend / "package.json").write_text('{"name":"host"}\n', encoding="utf-8")
    (host_distribution / "index.html").write_text("<html></html>\n", encoding="utf-8")

    package_root = host_project / ".venv" / "Lib" / "site-packages" / "opensprite"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    module_path = package_root / "integrations" / "web" / "adapter.py"

    unrelated_cwd = tmp_path / "elsewhere-installed"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)

    assert resolve_frontend_source_dir({}, module_path=module_path) is None
    assert resolve_frontend_dir({}, module_path=module_path) is None
