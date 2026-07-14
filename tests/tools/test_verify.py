import asyncio
import sys

from opensprite.tools import verify as verify_module
from opensprite.tools.verify import VerifyCommandResult, VerifyTool, classify_verification_result
from opensprite.tools.result_status import classify_tool_result_status


def test_verify_python_compile_passes_valid_files(tmp_path):
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool.execute(action="python_compile", path="."))

    assert result.startswith("Verification passed: python_compile")
    assert "Files checked: 1" in result


def test_verify_python_compile_reports_syntax_errors(tmp_path):
    (tmp_path / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool.execute(action="python_compile", path="."))
    status = classify_tool_result_status(result)
    verification = classify_verification_result(result)

    assert status.ok is False
    assert status.error_type == "VerifyToolError"
    assert status.category == "python_compile_failed"
    assert "Python compile verification failed" in status.error
    assert "bad.py" in status.error
    assert verification["status"] == "failed"
    assert verification["name"] == "python_compile"


def test_verify_rejects_paths_outside_workspace(tmp_path):
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool.execute(action="python_compile", path=".."))

    status = classify_tool_result_status(result)
    assert status.error_type == "ToolValidationError"
    assert status.category == "invalid_arguments"
    assert status.invalid_arguments is True
    assert "Verification path is outside the workspace" in status.error


def test_verify_rejects_unknown_action(tmp_path):
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool._execute(action="wat", path="."))
    status = classify_tool_result_status(result)

    assert status.error_type == "ToolValidationError"
    assert status.category == "invalid_arguments"
    assert status.invalid_arguments is True
    assert "Unknown verification action" in status.error
    assert classify_verification_result(result)["status"] == "error"


def test_verify_pytest_uses_focused_args(tmp_path):
    tool = VerifyTool(workspace=tmp_path)
    captured = {}

    async def fake_run_command(command, cwd, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return VerifyCommandResult(command=command, cwd=cwd, exit_code=0, output="1 passed")

    tool._run_command = fake_run_command

    result = asyncio.run(
        tool.execute(action="pytest", pytest_args=["tests/test_sample.py::test_ok"], timeout=7)
    )

    assert captured["command"] == [sys.executable, "-m", "pytest", "tests/test_sample.py::test_ok"]
    assert captured["cwd"] == tmp_path.resolve(strict=False)
    assert captured["timeout"] == 7
    assert result.startswith("Verification passed: pytest")


def test_verify_pytest_uses_nested_repo_as_project_root(tmp_path):
    repo = tmp_path / "repo"
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)
    captured = {}

    async def fake_run_command(command, cwd, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        return VerifyCommandResult(command=command, cwd=cwd, exit_code=0, output="1 passed")

    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="pytest", path="."))

    assert captured["command"] == [sys.executable, "-m", "pytest"]
    assert captured["cwd"] == repo.resolve(strict=False)
    assert result.startswith("Verification passed: pytest")


def test_verify_pytest_uses_project_relative_target(tmp_path):
    repo = tmp_path / "repo"
    target = repo / "tests" / "search"
    target.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)
    captured = {}

    async def fake_run_command(command, cwd, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        return VerifyCommandResult(command=command, cwd=cwd, exit_code=0, output="1 passed")

    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="pytest", path="repo/tests/search"))

    assert captured["command"] == [sys.executable, "-m", "pytest", "tests/search"]
    assert captured["cwd"] == repo.resolve(strict=False)
    assert result.startswith("Verification passed: pytest")


def test_verify_pytest_skips_when_no_tests_are_collected(tmp_path):
    tool = VerifyTool(workspace=tmp_path)

    async def fake_run_command(command, cwd, timeout):
        return VerifyCommandResult(
            command=command,
            cwd=cwd,
            exit_code=5,
            output="collected 0 items\n\n============================ no tests ran in 0.02s ============================",
        )

    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="pytest"))

    assert result.startswith("Verification skipped: pytest")
    assert "Exit code: 5" in result
    assert "no tests ran" in result
    assert not result.startswith("Error: Verification failed")


def test_verify_pytest_returns_structured_error_when_tests_fail(tmp_path):
    tool = VerifyTool(workspace=tmp_path)

    async def fake_run_command(command, cwd, timeout):
        return VerifyCommandResult(command=command, cwd=cwd, exit_code=1, output="1 failed")

    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="pytest"))
    status = classify_tool_result_status(result)
    verification = classify_verification_result(result)

    assert status.ok is False
    assert status.error_type == "VerifyToolError"
    assert status.category == "verification_failed"
    assert "Verification failed: pytest" in status.error
    assert "1 failed" in status.error
    assert verification["status"] == "failed"
    assert verification["name"] == "pytest"


def test_verify_pytest_returns_structured_error_when_timed_out(tmp_path):
    tool = VerifyTool(workspace=tmp_path)

    async def fake_run_command(command, cwd, timeout):
        return VerifyCommandResult(
            command=command,
            cwd=cwd,
            exit_code=None,
            output="Command timed out",
            timed_out=True,
        )

    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="pytest"))
    status = classify_tool_result_status(result)
    verification = classify_verification_result(result)

    assert status.ok is False
    assert status.error_type == "VerifyToolError"
    assert status.category == "verification_timed_out"
    assert "Verification timed out: pytest" in status.error
    assert verification["status"] == "timed_out"
    assert verification["name"] == "pytest"


def test_verify_web_build_uses_package_json_build_script(tmp_path):
    package_dir = tmp_path / "frontend"
    package_dir.mkdir(parents=True)
    (package_dir / "package.json").write_text('{"scripts":{"build":"vite build"}}', encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)
    captured = {}

    async def fake_run_command(command, cwd, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return VerifyCommandResult(command=command, cwd=cwd, exit_code=0, output="built")

    tool._resolve_npm_executable = lambda: "npm"
    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="web_build", timeout=9))

    assert captured["command"] == ["npm", "run", "build"]
    assert captured["cwd"] == package_dir.resolve(strict=False)
    assert captured["timeout"] == 9
    assert result.startswith("Verification passed: web_build")


def test_verify_web_build_reports_missing_package_json(tmp_path):
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool.execute(action="web_build"))
    status = classify_tool_result_status(result)

    assert status.error_type == "VerifyToolError"
    assert status.category == "package_json_not_found"
    assert "No package.json found" in status.error


def test_verify_web_build_reports_missing_script(tmp_path):
    package_dir = tmp_path / "frontend"
    package_dir.mkdir(parents=True)
    (package_dir / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool.execute(action="web_build"))
    status = classify_tool_result_status(result)

    assert status.error_type == "VerifyToolError"
    assert status.category == "package_script_missing"
    assert "scripts.build" in status.error


def test_verify_web_build_reports_missing_npm(tmp_path):
    package_dir = tmp_path / "frontend"
    package_dir.mkdir(parents=True)
    (package_dir / "package.json").write_text('{"scripts":{"build":"vite build"}}', encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)
    tool._resolve_npm_executable = lambda: None

    result = asyncio.run(tool.execute(action="web_build"))
    status = classify_tool_result_status(result)

    assert status.error_type == "VerifyToolError"
    assert status.category == "npm_unavailable"
    assert "npm was not found" in status.error


def test_verify_web_smoke_uses_package_json_smoke_script(tmp_path):
    package_dir = tmp_path / "frontend"
    package_dir.mkdir(parents=True)
    (package_dir / "package.json").write_text('{"scripts":{"test:smoke":"node smoke.mjs"}}', encoding="utf-8")
    tool = VerifyTool(workspace=tmp_path)
    captured = {}

    async def fake_run_command(command, cwd, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return VerifyCommandResult(command=command, cwd=cwd, exit_code=0, output="smoke ok")

    tool._resolve_npm_executable = lambda: "npm"
    tool._run_command = fake_run_command

    result = asyncio.run(tool.execute(action="web_smoke", timeout=11))

    assert captured["command"] == ["npm", "run", "test:smoke"]
    assert captured["cwd"] == package_dir.resolve(strict=False)
    assert captured["timeout"] == 11
    assert result.startswith("Verification passed: web_smoke")


def test_verify_reports_managed_process_startup_failure(tmp_path, monkeypatch):
    async def failing_start_exec_process(_command, *, cwd):
        assert cwd == str(tmp_path)
        raise RuntimeError("Unable to attach Windows command launcher to a Job Object")

    monkeypatch.setattr(verify_module, "start_exec_process", failing_start_exec_process)
    tool = VerifyTool(workspace=tmp_path)

    result = asyncio.run(tool._run_command(["verify-command"], tmp_path, 1))

    assert result.exit_code is None
    assert "Could not start verification command" in result.output
    assert "Windows command launcher" in result.output


def test_verify_command_cancellation_keeps_process_cleanup_alive(tmp_path, monkeypatch):
    async def scenario():
        communicate_started = asyncio.Event()
        communicate_finished = asyncio.Event()
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()
        terminate_calls = []

        class BlockingProcess:
            returncode = None

            async def communicate(self):
                communicate_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    communicate_finished.set()

        process = BlockingProcess()

        async def fake_start_exec_process(_command, *, cwd):
            assert cwd == str(tmp_path)
            return process

        async def fake_terminate_process_tree(candidate):
            terminate_calls.append(candidate)
            cleanup_started.set()
            await cleanup_release.wait()
            cleanup_finished.set()

        monkeypatch.setattr(verify_module, "start_exec_process", fake_start_exec_process)
        monkeypatch.setattr(verify_module, "terminate_process_tree", fake_terminate_process_tree)
        monkeypatch.setattr(verify_module, "_VERIFY_PROCESS_CLEANUP_TASKS", set())
        tool = VerifyTool(workspace=tmp_path)

        command_task = asyncio.create_task(tool._run_command(["verify-command"], tmp_path, 30))
        await asyncio.wait_for(communicate_started.wait(), timeout=1)
        command_task.cancel()
        await asyncio.wait_for(cleanup_started.wait(), timeout=1)
        command_task.cancel()
        try:
            await command_task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("verify cancellation was not preserved")

        assert cleanup_finished.is_set() is False
        cleanup_release.set()
        await asyncio.wait_for(cleanup_finished.wait(), timeout=1)
        await asyncio.sleep(0)
        return terminate_calls, communicate_finished.is_set(), verify_module._VERIFY_PROCESS_CLEANUP_TASKS

    terminate_calls, communicate_finished, cleanup_tasks = asyncio.run(scenario())

    assert len(terminate_calls) == 1
    assert communicate_finished is True
    assert cleanup_tasks == set()
