import asyncio
import json

from opensprite.tools.base import Tool
from opensprite.tools.batch import BatchTool
from opensprite.tools.registry import ToolRegistry
from opensprite.tools.result_status import classify_tool_result_status


class EchoTool(Tool):
    def __init__(self, name: str, prefix: str = "ok"):
        self._name = name
        self.prefix = prefix

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        }

    async def _execute(self, value: str, **kwargs):
        return f"{self.prefix}:{value}"


class JsonFailureTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "read"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    async def _execute(self, path: str, **kwargs):
        return json.dumps({"ok": False, "error": f"missing {path}"})


class SlowReadTool(Tool):
    def __init__(self):
        self.active = 0
        self.max_active = 0

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "read"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    async def _execute(self, path: str, **kwargs):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.02)
            return f"read:{path}"
        finally:
            self.active -= 1


def _registry_with_batch():
    registry = ToolRegistry()
    registry.register(EchoTool("read_file", "read"))
    registry.register(EchoTool("grep_files", "grep"))
    registry.register(EchoTool("write_file", "write"))
    registry.register(BatchTool(lambda: registry))
    return registry


def test_batch_runs_read_only_calls_and_preserves_order():
    registry = _registry_with_batch()

    result = asyncio.run(
        registry.execute(
            "batch",
            {
                "calls": [
                    {"tool": "grep_files", "arguments": {"value": "needle"}},
                    {"tool": "read_file", "arguments": {"value": "notes.txt"}},
                ]
            },
        )
    )

    payload = json.loads(result)
    assert payload["ok"] is True
    assert payload["summary"] == "Batch completed: 2 call(s), 0 failed."
    assert payload["results"][0]["tool"] == "grep_files"
    assert payload["results"][0]["result"] == "grep:needle"
    assert payload["results"][1]["tool"] == "read_file"
    assert payload["results"][1]["result"] == "read:notes.txt"


def test_batch_rejects_non_read_only_child_tools():
    registry = _registry_with_batch()

    result = asyncio.run(
        registry.execute(
            "batch",
            {"calls": [{"tool": "write_file", "arguments": {"value": "x"}}]},
        )
    )

    status = classify_tool_result_status(result)
    assert status.error_type == "ToolValidationError"
    assert status.category == "invalid_arguments"
    assert "Invalid arguments for batch" in status.error
    assert "calls[0].tool must be one of" in status.error
    assert "write:x" not in result


def test_batch_counts_structured_child_failures():
    registry = ToolRegistry()
    registry.register(JsonFailureTool())
    registry.register(BatchTool(lambda: registry))

    result = asyncio.run(
        registry.execute(
            "batch",
            {"calls": [{"tool": "read_file", "arguments": {"path": "missing.txt"}}]},
        )
    )

    status = classify_tool_result_status(result)
    payload = json.loads(result)
    assert status.error_type == "ToolFailure"
    assert payload["summary"] == "Batch completed: 1 call(s), 1 failed."
    assert payload["results"][0]["ok"] is False
    assert "missing missing.txt" in payload["results"][0]["result"]


def test_batch_enforces_call_limit():
    registry = _registry_with_batch()
    calls = [
        {"tool": "read_file", "arguments": {"value": f"file-{index}"}}
        for index in range(9)
    ]

    result = asyncio.run(registry.execute("batch", {"calls": calls}))

    status = classify_tool_result_status(result)
    assert status.error_type == "ToolValidationError"
    assert "batch supports at most 8 calls" in status.error


def test_batch_executes_children_concurrently():
    registry = ToolRegistry()
    slow_tool = SlowReadTool()
    registry.register(slow_tool)
    registry.register(BatchTool(lambda: registry))

    result = asyncio.run(
        registry.execute(
            "batch",
            {
                "calls": [
                    {"tool": "read_file", "arguments": {"path": "a.txt"}},
                    {"tool": "read_file", "arguments": {"path": "b.txt"}},
                ]
            },
        )
    )

    payload = json.loads(result)
    assert payload["summary"] == "Batch completed: 2 call(s), 0 failed."
    assert slow_tool.max_active == 2


def test_batch_truncates_large_child_results():
    registry = ToolRegistry()
    registry.register(EchoTool("read_file", "A" * 2500))
    registry.register(BatchTool(lambda: registry))

    result = asyncio.run(
        registry.execute(
            "batch",
            {"calls": [{"tool": "read_file", "arguments": {"value": "x"}}]},
        )
    )

    payload = json.loads(result)
    assert "result truncated" in payload["results"][0]["result"]
    assert len(result) < 3000
