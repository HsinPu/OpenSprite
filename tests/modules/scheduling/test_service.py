import asyncio
import json
import shutil

from opensprite.integrations.workspace.paths import get_session_workspace
from opensprite.modules.scheduling.manager import CronManager, CronSessionResetInProgress
from opensprite.modules.scheduling.service import CronService
from opensprite.modules.scheduling.types import CronJob, CronSchedule


def _make_cron_manager(workspace_root, on_job):
    return CronManager(
        workspace_root=workspace_root,
        workspace_for_session=lambda session_id: get_session_workspace(
            session_id,
            workspace_root=workspace_root,
        ),
        on_job=on_job,
    )


def test_cron_service_persists_session_and_jobs(tmp_path):
    store_path = tmp_path / "cron" / "jobs.json"
    service = CronService(store_path, session_id="telegram:user-a")

    service.add_job(
        name="reminder",
        schedule=CronSchedule(kind="every", every_ms=60_000),
        message="ping",
        deliver=True,
        channel="telegram",
        external_chat_id="user-a",
    )

    data = json.loads(store_path.read_text(encoding="utf-8"))

    assert data["sessionId"] == "telegram:user-a"
    assert data["jobs"][0]["payload"]["message"] == "ping"
    assert data["jobs"][0]["payload"]["externalChatId"] == "user-a"


def test_cron_service_runs_one_shot_job_and_removes_it(tmp_path):
    calls = []

    async def on_job(job: CronJob):
        calls.append(job.id)
        return "ok"

    async def scenario():
        service = CronService(tmp_path / "cron" / "jobs.json", session_id="telegram:user-a", on_job=on_job)
        job = service.add_job(
            name="once",
            schedule=CronSchedule(kind="at", at_ms=1),
            message="once",
            delete_after_run=True,
        )
        await service.run_job(job.id)
        return service.list_jobs(include_disabled=True)

    jobs = asyncio.run(scenario())

    assert calls != []
    assert jobs == []


def test_cron_manager_keeps_jobs_in_separate_session_files(tmp_path):
    async def on_job(session_id: str, job: CronJob):
        return f"{session_id}:{job.id}"

    async def scenario():
        manager = _make_cron_manager(tmp_path / "workspace", on_job)
        service_a = await manager.get_or_create_service("telegram:user-a")
        service_b = await manager.get_or_create_service("telegram:user-b")
        service_a.add_job("job-a", CronSchedule(kind="every", every_ms=1_000), "A")
        service_b.add_job("job-b", CronSchedule(kind="every", every_ms=1_000), "B")
        await manager.stop()
        return service_a.store_path, service_b.store_path

    path_a, path_b = asyncio.run(scenario())

    assert path_a != path_b
    assert path_a.exists()
    assert path_b.exists()
    assert json.loads(path_a.read_text(encoding="utf-8"))["sessionId"] == "telegram:user-a"
    assert json.loads(path_b.read_text(encoding="utf-8"))["sessionId"] == "telegram:user-b"


def test_cron_manager_uses_the_injected_session_workspace_without_rewriting_id(tmp_path):
    requested_session_ids = []
    resolved_workspace = tmp_path / "resolved-session"

    def workspace_for_session(session_id: str):
        requested_session_ids.append(session_id)
        resolved_workspace.mkdir(parents=True, exist_ok=True)
        return resolved_workspace

    async def on_job(session_id: str, job: CronJob):
        return f"{session_id}:{job.id}"

    async def scenario():
        manager = CronManager(
            workspace_root=tmp_path / "workspace",
            workspace_for_session=workspace_for_session,
            on_job=on_job,
        )
        service = await manager.get_or_create_service("telegram:room:thread")
        await manager.stop()
        return service.store_path

    store_path = asyncio.run(scenario())

    assert requested_session_ids == ["telegram:room:thread"]
    assert store_path == resolved_workspace / "cron" / "jobs.json"


def test_cron_manager_quiesces_one_session_until_reset_finishes(tmp_path):
    calls = []

    async def on_job(session_id: str, job: CronJob):
        calls.append((session_id, job.id))
        return "ok"

    async def scenario():
        manager = _make_cron_manager(tmp_path / "workspace", on_job)
        service_a = await manager.get_or_create_service("telegram:user-a")
        service_b = await manager.get_or_create_service("telegram:user-b")
        service_a.add_job(
            "soon",
            CronSchedule(kind="every", every_ms=60_000),
            "A",
        )
        service_b.add_job("later", CronSchedule(kind="every", every_ms=60_000), "B")
        path_a = service_a.store_path
        path_b = service_b.store_path
        timer_task = service_a._timer_task

        async with manager.quiesce_session("telegram:user-a"):
            try:
                await manager.get_or_create_service("telegram:user-a")
            except CronSessionResetInProgress as exc:
                blocked_session_id = exc.session_id
            else:
                blocked_session_id = None
            if path_a.parents[1].exists():
                shutil.rmtree(path_a.parents[1])
            await asyncio.sleep(0)
            services_during_reset = await manager.get_all_services()
        services = await manager.get_all_services()
        await manager.stop()
        return (
            path_a,
            path_b,
            services,
            services_during_reset,
            timer_task,
            blocked_session_id,
        )

    (
        path_a,
        path_b,
        services,
        services_during_reset,
        timer_task,
        blocked_session_id,
    ) = asyncio.run(scenario())

    assert calls == []
    assert timer_task is not None
    assert timer_task.done()
    assert blocked_session_id == "telegram:user-a"
    assert path_a.exists() is False
    assert path_b.exists() is True
    assert set(services_during_reset) == {"telegram:user-b"}
    assert set(services) == {"telegram:user-b"}


def test_cron_manager_does_not_discover_legacy_chats_directory(tmp_path):
    async def on_job(session_id: str, job: CronJob):
        return f"{session_id}:{job.id}"

    async def scenario():
        workspace_root = tmp_path / "workspace"
        legacy_path = workspace_root / "chats" / "telegram" / "user-a" / "cron" / "jobs.json"
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text(
            json.dumps({"version": 1, "sessionId": "telegram:user-a", "jobs": []}),
            encoding="utf-8",
        )
        manager = _make_cron_manager(workspace_root, on_job)
        await manager.start()
        services = await manager.get_all_services()
        await manager.stop()
        return services, workspace_root / "sessions"

    services, sessions_root = asyncio.run(scenario())

    assert services == {}
    assert sessions_root.exists() is False


def test_cron_manager_serializes_concurrent_session_resets(tmp_path):
    async def on_job(session_id: str, job: CronJob):
        return f"{session_id}:{job.id}"

    async def scenario():
        manager = _make_cron_manager(tmp_path / "workspace", on_job)
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        second_entered = asyncio.Event()

        async def first_reset():
            async with manager.quiesce_session("web:chat-1"):
                first_entered.set()
                await release_first.wait()

        async def second_reset():
            await first_entered.wait()
            async with manager.quiesce_session("web:chat-1"):
                second_entered.set()

        first_task = asyncio.create_task(first_reset())
        second_task = asyncio.create_task(second_reset())
        await first_entered.wait()
        await asyncio.sleep(0)
        second_was_blocked = not second_entered.is_set()
        release_first.set()
        await asyncio.gather(first_task, second_task)
        await manager.stop()
        return second_was_blocked, second_entered.is_set()

    second_was_blocked, second_completed = asyncio.run(scenario())

    assert second_was_blocked is True
    assert second_completed is True
