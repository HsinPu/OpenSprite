import asyncio

from agent_test_helpers import make_agent_loop
from opensprite.tools.result_status import classify_tool_result_status


def test_run_verify_reports_missing_run_context(tmp_path):
    agent = make_agent_loop(tmp_path)

    result = asyncio.run(agent.run_verify(action="pytest"))
    status = classify_tool_result_status(result.content)

    assert result.had_tool_error is True
    assert status.ok is False
    assert status.error_type == "VerifyToolError"
    assert status.category == "missing_run_context"
    assert "No active run is available" in status.error
