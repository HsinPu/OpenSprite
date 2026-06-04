import asyncio

from opensprite.bus.message import AssistantMessage
from opensprite.evals.task_completion import (
    evaluate_task_completion_case,
    run_live_task_completion_eval,
    run_task_completion_smoke,
)
from opensprite.runs.events import COMPLETION_GATE_EVALUATED_EVENT
from opensprite.runs.lifecycle import RUN_FINISHED_EVENT
from opensprite.storage import MemoryStorage, StoredMessage


def test_task_completion_case_passes_required_checks():
    payload = evaluate_task_completion_case(
        {
            "id": "answer",
            "label": "Answer case",
            "prompt": "How do I run the web smoke check?",
            "expected_completion_status": "complete",
            "must_include": ["apps/web", "npm run test:smoke"],
            "must_not_include": ["Playwright"],
            "require_no_tool_error": True,
        },
        {
            "response_text": "Run npm run test:smoke from apps/web.",
            "completion_status": "complete",
            "had_tool_error": False,
        },
    )

    assert payload["ok"] is True
    assert payload["score"] == {"passed": 6, "total": 6}
    assert all(check["ok"] for check in payload["checks"])


def test_task_completion_case_reports_failed_checks():
    payload = evaluate_task_completion_case(
        {
            "id": "answer",
            "expected_completion_status": "complete",
            "must_include": ["required fact"],
            "must_not_include": ["forbidden claim"],
            "require_no_tool_error": True,
        },
        {
            "response_text": "This includes a forbidden claim.",
            "completion_status": "incomplete",
            "had_tool_error": True,
        },
    )

    failed_check_ids = {check["id"] for check in payload["checks"] if not check["ok"]}
    assert payload["ok"] is False
    assert failed_check_ids == {
        "completion_status",
        "tool_errors",
        "must_include_required_fact",
        "must_not_include_forbidden_claim",
    }


def test_task_completion_case_requires_response_ending():
    passing = evaluate_task_completion_case(
        {
            "id": "ending",
            "expected_completion_status": "complete",
            "must_end_with": "final line",
        },
        {
            "response_text": "first line\nfinal line",
            "completion_status": "complete",
            "had_tool_error": False,
        },
    )
    failing = evaluate_task_completion_case(
        {
            "id": "ending",
            "expected_completion_status": "complete",
            "must_end_with": "final line",
        },
        {
            "response_text": "first line\nfinal line\nextra text",
            "completion_status": "complete",
            "had_tool_error": False,
        },
    )

    assert passing["ok"] is True
    assert failing["ok"] is False
    assert "must_end_with_final_line" in {check["id"] for check in failing["checks"] if not check["ok"]}


def test_task_completion_case_requires_exact_response():
    passing = evaluate_task_completion_case(
        {"id": "exact", "exact_response": "alpha beta gamma"},
        {"response_text": "alpha beta gamma"},
    )
    failing = evaluate_task_completion_case(
        {"id": "exact", "exact_response": "alpha beta gamma"},
        {"response_text": "alpha beta gamma."},
    )

    assert passing["ok"] is True
    assert failing["ok"] is False
    assert "exact_response" in {check["id"] for check in failing["checks"] if not check["ok"]}


def test_task_completion_case_requires_non_empty_line_count():
    passing = evaluate_task_completion_case(
        {"id": "lines", "expected_non_empty_lines": 2},
        {"response_text": "first\n\nsecond"},
    )
    failing = evaluate_task_completion_case(
        {"id": "lines", "expected_non_empty_lines": 2},
        {"response_text": "first\nsecond\nthird"},
    )

    assert passing["ok"] is True
    assert failing["ok"] is False
    assert "expected_non_empty_lines" in {check["id"] for check in failing["checks"] if not check["ok"]}


def test_task_completion_smoke_runs_fixed_cases():
    payload = run_task_completion_smoke()

    assert payload["ok"] is True
    assert payload["live"] is False
    assert payload["summary"] == {
        "passed_cases": 2,
        "total_cases": 2,
        "passed_checks": 15,
        "total_checks": 15,
    }
    assert {case["id"] for case in payload["cases"]} == {"web_smoke_question", "task_completion_question"}


def test_live_task_completion_eval_scores_agent_result():
    asyncio.run(_run_live_task_completion_eval_scores_agent_result())


async def _run_live_task_completion_eval_scores_agent_result():
    storage = MemoryStorage()

    class LiveEvalAgent:
        def __init__(self):
            self.storage = storage
            self.seen_messages = []

        async def process(self, user_message):
            self.seen_messages.append(user_message)
            case_id = user_message.metadata["eval_case_id"]
            run_id = f"run-{case_id}"
            response_text = {
                "literal_instruction": "alpha beta gamma",
                "multi_step_completion": (
                    "1. 問題：這是格式遵循測試。\n"
                    "2. 可能原因：模型可能漏掉步驟；輸出格式可能不穩定。\n"
                    "3. 結論：已完成三步驟回答"
                ),
                "exact_two_line_output": "狀態：完成\n代碼：A7-42",
                "exact_json_output": '{"status":"complete","items":["alpha","beta"]}',
            }[case_id]
            await storage.create_run(user_message.session_id, run_id, status="running", created_at=1.0)
            await storage.add_run_event(
                user_message.session_id,
                run_id,
                COMPLETION_GATE_EVALUATED_EVENT,
                payload={"status": "complete", "reason": "test"},
                created_at=2.0,
            )
            await storage.add_run_event(
                user_message.session_id,
                run_id,
                RUN_FINISHED_EVENT,
                payload={"status": "completed", "had_tool_error": False},
                created_at=3.0,
            )
            await storage.update_run_status(
                user_message.session_id,
                run_id,
                "completed",
                metadata={"had_tool_error": False},
                finished_at=3.0,
            )
            return AssistantMessage(
                text=response_text,
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
            )

    agent = LiveEvalAgent()
    model_info = {"provider_id": "test-provider", "provider": "test", "model": "test-model", "configured": True}
    payload = await run_live_task_completion_eval(
        agent=agent,
        storage=storage,
        channel="web",
        timeout_seconds=1,
        model_info=model_info,
    )

    assert payload["ok"] is True
    assert payload["live"] is True
    assert payload["model"] == model_info
    assert payload["batch_id"].startswith("eval_batch_")
    assert payload["summary"]["passed_cases"] == payload["summary"]["total_cases"] == 4
    assert payload["summary"]["passed_checks"] == payload["summary"]["total_checks"]
    assert agent.seen_messages[0].metadata == {
        "eval_kind": "task_completion",
        "eval_case_id": "literal_instruction",
        "eval_batch_id": payload["batch_id"],
        "eval_model": model_info,
    }
    assert agent.seen_messages[1].metadata == {
        "eval_kind": "task_completion",
        "eval_case_id": "multi_step_completion",
        "eval_batch_id": payload["batch_id"],
        "eval_model": model_info,
    }
    cases_by_id = {case["id"]: case for case in payload["cases"]}
    assert set(cases_by_id) == {
        "literal_instruction",
        "multi_step_completion",
        "exact_two_line_output",
        "exact_json_output",
    }
    assert cases_by_id["literal_instruction"]["run_id"] == "run-literal_instruction"
    assert cases_by_id["literal_instruction"]["eval_id"].startswith("eval_")
    assert cases_by_id["literal_instruction"]["label"] == "Literal instruction answer"
    assert cases_by_id["literal_instruction"]["expected_summary"] == "alpha beta gamma"
    assert {case["batch_id"] for case in cases_by_id.values()} == {payload["batch_id"]}
    assert cases_by_id["literal_instruction"]["completion_status"] == "complete"
    assert cases_by_id["literal_instruction"]["response_preview"] == "alpha beta gamma"
    assert cases_by_id["literal_instruction"]["model"] == model_info
    assert cases_by_id["multi_step_completion"]["run_id"] == "run-multi_step_completion"
    assert cases_by_id["multi_step_completion"]["response_preview"].endswith("3. 結論：已完成三步驟回答")
    assert cases_by_id["exact_two_line_output"]["response_preview"] == "狀態：完成\n代碼：A7-42"
    assert cases_by_id["exact_json_output"]["response_preview"] == '{"status":"complete","items":["alpha","beta"]}'
    history = await storage.list_eval_runs(kind="task_completion", limit=10)
    assert len(history) == 4
    assert {item.metadata["batch_id"] for item in history} == {payload["batch_id"]}
    history_by_case = {item.case_id: item for item in history}
    assert history_by_case["literal_instruction"].eval_id == cases_by_id["literal_instruction"]["eval_id"]
    assert history_by_case["literal_instruction"].summary["text"] == cases_by_id["literal_instruction"]["summary"]
    assert history_by_case["literal_instruction"].response_preview == "alpha beta gamma"
    assert history_by_case["literal_instruction"].metadata["case_label"] == "Literal instruction answer"
    assert history_by_case["literal_instruction"].metadata["expected_summary"] == "alpha beta gamma"
    assert history_by_case["literal_instruction"].metadata["actual_response"] == "alpha beta gamma"
    assert history_by_case["literal_instruction"].metadata["model"] == model_info
    assert history_by_case["multi_step_completion"].eval_id == cases_by_id["multi_step_completion"]["eval_id"]


def test_live_task_completion_eval_uses_stored_response_when_agent_return_is_empty():
    asyncio.run(_run_live_task_completion_eval_uses_stored_response_when_agent_return_is_empty())


async def _run_live_task_completion_eval_uses_stored_response_when_agent_return_is_empty():
    storage = MemoryStorage()

    class EmptyReturnAgent:
        async def process(self, user_message):
            case_id = user_message.metadata["eval_case_id"]
            run_id = f"run-{case_id}"
            response_text = {
                "literal_instruction": "alpha beta gamma",
                "multi_step_completion": (
                    "1. 問題：這是格式遵循測試。\n"
                    "2. 可能原因：模型可能漏掉步驟；輸出格式可能不穩定。\n"
                    "3. 結論：已完成三步驟回答"
                ),
                "exact_two_line_output": "狀態：完成\n代碼：A7-42",
                "exact_json_output": '{"status":"complete","items":["alpha","beta"]}',
            }[case_id]
            await storage.create_run(user_message.session_id, run_id, status="running", created_at=1.0)
            await storage.add_run_part(
                user_message.session_id,
                run_id,
                "assistant_message",
                content=response_text,
                created_at=2.0,
            )
            await storage.add_message(
                user_message.session_id,
                StoredMessage(role="assistant", content=response_text, timestamp=2.0),
            )
            await storage.add_run_event(
                user_message.session_id,
                run_id,
                COMPLETION_GATE_EVALUATED_EVENT,
                payload={"status": "complete", "reason": "test"},
                created_at=3.0,
            )
            await storage.add_run_event(
                user_message.session_id,
                run_id,
                RUN_FINISHED_EVENT,
                payload={"status": "completed", "had_tool_error": False},
                created_at=4.0,
            )
            await storage.update_run_status(
                user_message.session_id,
                run_id,
                "completed",
                metadata={"had_tool_error": False},
                finished_at=4.0,
            )
            return AssistantMessage(
                text="",
                channel=user_message.channel,
                external_chat_id=user_message.external_chat_id,
                session_id=user_message.session_id,
            )

    payload = await run_live_task_completion_eval(
        agent=EmptyReturnAgent(),
        storage=storage,
        channel="web",
        timeout_seconds=1,
        model_info={"provider_id": "test-provider", "provider": "test", "model": "test-model", "configured": True},
    )

    assert payload["ok"] is True
    cases_by_id = {case["id"]: case for case in payload["cases"]}
    assert cases_by_id["exact_json_output"]["actual_response"] == '{"status":"complete","items":["alpha","beta"]}'
    assert cases_by_id["exact_json_output"]["response_source"] == "run_part"
    history = await storage.list_eval_runs(kind="task_completion", limit=10)
    history_by_case = {item.case_id: item for item in history}
    assert history_by_case["exact_json_output"].metadata["actual_response"] == '{"status":"complete","items":["alpha","beta"]}'
    assert history_by_case["exact_json_output"].metadata["response_source"] == "run_part"
