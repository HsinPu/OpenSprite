"""Ripgrep process runtime behavior."""

import asyncio

from opensprite.integrations.processes import ripgrep


class _FakeProcess:
    def __init__(self, *, returncode: int | None, output: tuple[bytes, bytes]):
        self.returncode = returncode
        self.output = output
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.output

    def kill(self) -> None:
        self.killed = True


def test_find_ripgrep_delegates_to_path_lookup(monkeypatch):
    calls = []
    monkeypatch.setattr(ripgrep.shutil, "which", lambda executable: calls.append(executable) or "/tools/rg")

    assert ripgrep.find_ripgrep() == "/tools/rg"
    assert calls == ["rg"]


def test_run_ripgrep_uses_direct_process_with_hidden_window_options(tmp_path, monkeypatch):
    calls = []
    process = _FakeProcess(returncode=7, output=(b"out\xff", b"err\xff"))

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(ripgrep.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(ripgrep, "windows_hidden_process_kwargs", lambda: {"creationflags": 123})

    result = asyncio.run(
        ripgrep.run_ripgrep(["rg", "needle"], tmp_path, timeout_seconds=12.5)
    )

    assert result == (7, "out�", "err�")
    assert calls == [
        (
            ("rg", "needle"),
            {
                "cwd": str(tmp_path),
                "stdout": ripgrep.asyncio.subprocess.PIPE,
                "stderr": ripgrep.asyncio.subprocess.PIPE,
                "creationflags": 123,
            },
        )
    ]


def test_run_ripgrep_kills_timed_out_process_and_returns_timeout_message(tmp_path, monkeypatch):
    process = _FakeProcess(returncode=None, output=(b"partial", b""))

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    async def fake_wait_for(awaitable, *, timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(ripgrep.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(ripgrep.asyncio, "wait_for", fake_wait_for)

    result = asyncio.run(
        ripgrep.run_ripgrep(["rg", "needle"], tmp_path, timeout_seconds=0.25)
    )

    assert process.killed is True
    assert result == (124, "partial", "ripgrep timed out")
