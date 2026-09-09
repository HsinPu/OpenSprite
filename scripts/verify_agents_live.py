"""Explicit real-provider delegation probe; never modifies installed user data."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx
from opensprite_backend.agent.loop import AgentLoop
from opensprite_backend.conversations.sqlite_repository import SqliteConversationRepository
from opensprite_backend.conversations.models import RunStatus
from opensprite_backend.custom_agents.child_executor import ChildAgentExecutor
from opensprite_backend.custom_agents.child_repository import ChildExecutionRepository
from opensprite_backend.custom_agents.delegation import DelegationCoordinator
from opensprite_backend.custom_agents.definition import parse_agent_definition
from opensprite_backend.custom_agents.models import AgentCandidate, AgentExecutionSnapshot, AgentRecord
from opensprite_backend.inference.capabilities import ModelCapability
from opensprite_backend.provider_runtime import create_provider_runtime
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
    if not model:
        raise SystemExit("No configured model; live verification unavailable")
    runtime = create_provider_runtime()
    try:
        with TemporaryDirectory(prefix="opensprite-agents-probe-") as temporary:
            repository = SqliteConversationRepository(Path(temporary) / "probe.sqlite")
            store = ChildExecutionRepository(Path(temporary) / "probe.sqlite")
            definition = parse_agent_definition(b'name = "invoice-auditor"\ndescription = "Specialist for independent review of invoice duplicates and billing totals. Do not use for unrelated arithmetic."\ndeveloper_instructions = "Review the supplied invoice data. Start your report with AGENT_PROBE_OK and report duplicate invoice IDs and amount issues. No tools or external data are needed."\n')
            record = AgentRecord(id=str(uuid4()), scope="global", workspaceId=None,
                                 fileName="invoice-auditor.toml", name=definition.name,
                                 revision=1, enabled=True)
            snapshot = AgentExecutionSnapshot((AgentCandidate(record, definition),))
            cases = [
                ("explicit", "請委派 invoice-auditor 稽核發票 A-1 100元、A-1 100元，等待報告後摘要結果。", True),
                ("discovery", "請找適合的專家獨立檢查這組帳單：B-2 50元、B-2 50元。收回專家報告後告訴我有沒有重複請款。", True),
                ("negative", "請直接回答 2 加 2，不需要委派其他代理。", False),
            ]
            rows = []
            for name, message, expected in cases:
                run = repository.start_run(conversation_id=None, client_request_id=str(uuid4()),
                    message=message, provider_id=model["providerId"], model_id=model["modelId"],
                    response_mode="default", output_continuation="off").run
                coordinator = DelegationCoordinator(store, ChildAgentExecutor(runtime.model_gateway, ProbeBudget(), store))
                loop = AgentLoop(repository=repository, gateway=runtime.model_gateway,
                    tools=ToolRegistry((), policy=ReadOnlyToolPolicy()), capability_resolver=ProbeBudget(),
                    delegation=coordinator)
                try:
                    result = await asyncio.wait_for(loop.execute(run.id, asyncio.Event(), agents=snapshot), 90)
                    children = store.list(run.id)
                    row = {"case": name, "completed": result.status is RunStatus.COMPLETED,
                           "childCount": len(children), "expectedDelegation": expected,
                           "childrenCompleted": all(child.status == "completed" for child in children),
                           "roleObserved": any("AGENT_PROBE_OK" in child.result_text for child in children)}
                    rows.append(row)
                    print(json.dumps(row), flush=True)
                finally:
                    await coordinator.close()
            if not all(row["completed"] and bool(row["childCount"]) == row["expectedDelegation"]
                       and row["childrenCompleted"] and (not row["expectedDelegation"] or row["roleObserved"])
                       for row in rows):
                raise SystemExit("Live delegation probe did not meet acceptance criteria")
    finally:
        await runtime.aclose()


if __name__ == "__main__":
    asyncio.run(main())
