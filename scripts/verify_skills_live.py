"""Explicit opt-in real-model Skill routing probe; isolated DB, no installation writes."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx
from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.models import RunEventType, RunStatus
from opensprite_backend.inference.capabilities import ModelCapability
from opensprite_backend.provider_runtime import create_provider_runtime
from opensprite_backend.skills.models import SkillContent, SkillExecutionSnapshot
from opensprite_backend.tools.registry import ToolRegistry
from opensprite_backend.tools.policy import ReadOnlyToolPolicy


class ProbeBudget:
    async def resolve(self, provider_id, model_id):
        return ModelCapability(provider_id, model_id, "Probe", 32768, 512)


async def main():
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get("http://localhost:8765/api/settings/ai")
        response.raise_for_status()
        model = response.json()["model"]
    runtime = create_provider_runtime()
    try:
        with TemporaryDirectory(prefix="opensprite-skills-probe-") as temporary:
            repository = SqliteConversationRepository(Path(temporary) / "probe.sqlite")
            skill = SkillContent(str(uuid4()), "global", "invoice-audit", "Use when auditing invoices for duplicate charges or mismatched totals; not for unrelated arithmetic or general questions.", 1, "a" * 64,
                                 "For invoice audits, start your answer with SKILL_PROBE_OK, list duplicates and total discrepancies, and explain missing data. Do not access files or perform writes.")
            snapshot = SkillExecutionSnapshot((skill,))
            cases = [("positive", "請稽核以下發票是否重複請款：A-1 100元、A-1 100元。", True),
                     ("near", "我收到兩張相同編號 B-2 各 50 元的帳單，可以幫我找出請款問題嗎？", True),
                     ("negative", "請只回答：2 加 2 等於多少？", False)]
            results = []
            for name, message, expected in cases:
                run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()), message=message,
                                           provider_id=model["providerId"], model_id=model["modelId"], response_mode="default", output_continuation="off").run
                loop = AgentLoop(repository=repository, gateway=runtime.model_gateway,
                                 tools=ToolRegistry([], policy=ReadOnlyToolPolicy()), capability_resolver=ProbeBudget())
                result = await asyncio.wait_for(loop.execute(run.id, asyncio.Event(), skills=snapshot), timeout=90)
                events = repository.list_run_events(run.id, after_sequence=0, limit=100)
                loaded = any(event.type is RunEventType.SKILL_LOADED for event in events)
                row = {"case": name, "completed": result.status is RunStatus.COMPLETED, "loaded": loaded,
                       "expected": expected, "instructionObserved": "SKILL_PROBE_OK" in result.partial_text}
                results.append(row)
                print(json.dumps(row), flush=True)
            if not all(row["completed"] and row["loaded"] == row["expected"] and (not row["expected"] or row["instructionObserved"]) for row in results):
                raise SystemExit("Probe did not meet acceptance criteria")
    finally:
        await runtime.aclose()


if __name__ == "__main__":
    asyncio.run(main())
