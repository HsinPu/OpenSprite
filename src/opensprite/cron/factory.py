"""Cron manager factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..bus.message import UserMessage
from ..context.paths import split_session_id
from .manager import CronManager
from .types import CronJob


def create_cron_manager(config: Any, agent: Any, mq: Any) -> CronManager:
    """Create the per-session cron manager bound to the running agent."""

    async def on_job(session_id: str, job: CronJob) -> str | None:
        channel, raw_external_chat_id = split_session_id(session_id)
        user_message = UserMessage(
            text=job.payload.message,
            channel=job.payload.channel or channel,
            external_chat_id=job.payload.external_chat_id or raw_external_chat_id,
            session_id=session_id,
            sender_id="system:cron",
            sender_name="cron",
            metadata={
                "source": "cron",
                "job_id": job.id,
                "_bypass_commands": True,
                "_suppress_outbound": not job.payload.deliver,
            },
        )
        await mq.enqueue(user_message)
        return None

    return CronManager(
        workspace_root=Path(agent.tool_workspace or Path.home() / ".opensprite" / "workspace"),
        on_job=on_job,
    )
