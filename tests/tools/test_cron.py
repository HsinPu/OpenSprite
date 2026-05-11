import asyncio
import json
import time

from opensprite.cron.manager import CronManager
from opensprite.cron.service import CronService
from opensprite.cron.types import CronJob
from opensprite.tools.cron import CronTool


def test_cron_tool_add_list_and_remove(tmp_path):
    async def on_job(session_id: str, job: CronJob):
        return "ok"

    async def scenario():
        manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        tool = CronTool(manager, get_session_id=lambda: "telegram:user-a")

        created = await tool.execute(
            action="add",
            name="check-weather",
            message="Check weather and report back",
            every_seconds=300,
            deliver=True,
        )
        listed = await tool.execute(action="list")
        service = await manager.get_or_create_service("telegram:user-a")
        job_id = service.list_jobs(include_disabled=True)[0].id
        removed = await tool.execute(action="remove", job_id=job_id)
        listed_after = await tool.execute(action="list")
        await manager.stop()
        return created, listed, removed, listed_after

    created, listed, removed, listed_after = asyncio.run(scenario())

    assert "Created job 'check-weather'" in created
    assert "Scheduled jobs:" in listed
    assert "check-weather" in listed
    assert "every 5m" in listed
    assert removed.startswith("Removed job ")
    assert listed_after == "No scheduled jobs."


def test_cron_tool_can_pause_enable_and_run(tmp_path):
    executions = []

    async def on_job(session_id: str, job: CronJob):
        executions.append((session_id, job.id))
        return "ok"

    async def scenario():
        manager = CronManager(workspace_root=tmp_path / "workspace", on_job=on_job)
        tool = CronTool(manager, get_session_id=lambda: "telegram:user-a")

        await tool.execute(
            action="add",
            name="check-weather",
            message="Check weather and report back",
            every_seconds=300,
            deliver=True,
        )
        service = await manager.get_or_create_service("telegram:user-a")
        job_id = service.list_jobs(include_disabled=True)[0].id

        paused = await tool.execute(action="pause", job_id=job_id)
        enabled = await tool.execute(action="enable", job_id=job_id)
        ran = await tool.execute(action="run", job_id=job_id)
        await manager.stop()
        return paused, enabled, ran, job_id, service.get_job(job_id)

    paused, enabled, ran, job_id, job = asyncio.run(scenario())

    assert paused == f"Paused job {job_id}"
    assert enabled == f"Enabled job {job_id}"
    assert ran == f"Ran job {job_id}"
    assert executions == [("telegram:user-a", job_id)]
    assert job is not None
    assert job.enabled is True


def test_cron_service_runs_persisted_due_job_on_start(tmp_path):
    async def scenario():
        executions = []
        now_ms = int(time.time() * 1000)
        store_path = tmp_path / "cron" / "jobs.json"
        store_path.parent.mkdir(parents=True)
        store_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "sessionId": "telegram:user-a",
                    "jobs": [
                        {
                            "id": "job-due",
                            "name": "due job",
                            "enabled": True,
                            "schedule": {
                                "kind": "every",
                                "atMs": None,
                                "everyMs": 60_000,
                                "expr": None,
                                "tz": None,
                            },
                            "payload": {
                                "message": "Run missed work",
                                "deliver": False,
                                "channel": None,
                                "externalChatId": None,
                            },
                            "state": {
                                "nextRunAtMs": now_ms - 1,
                                "lastRunAtMs": None,
                                "lastStatus": None,
                                "lastError": None,
                                "runHistory": [],
                            },
                            "createdAtMs": now_ms - 60_000,
                            "updatedAtMs": now_ms - 60_000,
                            "deleteAfterRun": False,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        async def on_job(job: CronJob):
            executions.append(job.id)
            return "ok"

        service = CronService(store_path, session_id="telegram:user-a", on_job=on_job)
        await service.start()
        deadline = time.time() + 1
        while not executions and time.time() < deadline:
            await asyncio.sleep(0.01)
        service.stop()
        saved = json.loads(store_path.read_text(encoding="utf-8"))
        return executions, saved, now_ms

    executions, saved, now_ms = asyncio.run(scenario())

    assert executions == ["job-due"]
    state = saved["jobs"][0]["state"]
    assert state["lastStatus"] == "ok"
    assert state["lastRunAtMs"] >= now_ms
    assert state["nextRunAtMs"] > now_ms
    assert state["runHistory"][-1]["status"] == "ok"
