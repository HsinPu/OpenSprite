"""CLI smoke runner for end-to-end Web chat traces."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import typer

from ..storage.base import StoredRunTrace
from ..storage.sqlite import SQLiteStorage
from .commands_chat import _json_for_stdout, run_web_chat


WEB_TOOL_NAMES = {"web_search", "web_fetch", "web_research"}
REMOVED_TOOL_NAMES = {"search_knowledge"}


@dataclass(frozen=True)
class SmokeCase:
    case_id: str
    prompt: str
    expect_web_tools: bool | None = None


DEFAULT_SMOKE_CASES: tuple[SmokeCase, ...] = (
    SmokeCase("pong", "請只回覆 pong。", expect_web_tools=False),
    SmokeCase("summary-no-web", "用三點列出 OpenSprite 可以幫使用者做什麼，不要上網。", expect_web_tools=False),
    SmokeCase("math", "請計算 17 * 23 + 19，最後只輸出答案。", expect_web_tools=False),
    SmokeCase("translate", "請把這句翻成英文：今天我想測試 CLI 對話流程。", expect_web_tools=False),
    SmokeCase("runtime-context", "請回答你目前看到的 channel、session id、current time。", expect_web_tools=False),
    SmokeCase("direct-debug", "請說明 debug Python ModuleNotFoundError 的前三個檢查步驟，不要上網。", expect_web_tools=False),
    SmokeCase("trace-metric", "請用一句話總結 CLI chat trace 最該觀察的指標。", expect_web_tools=False),
    SmokeCase("web-search", "請務必使用 web_search 搜尋 OpenAI 2026 最新消息，回覆一個來源網址即可。", expect_web_tools=True),
    SmokeCase(
        "web-research",
        "請務必使用 web_research 搜尋 2026 AI agent tools market trends，整理兩點並列出來源網址。",
        expect_web_tools=True,
    ),
    SmokeCase(
        "current-source",
        "請上網查詢 2026 AI agent tools market trends，最多整理三個來源網址。",
        expect_web_tools=True,
    ),
)


SendWebChat = Callable[..., Awaitable[dict[str, Any]]]


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _tool_name_from_event(event_payload: dict[str, Any]) -> str:
    value = _payload_value(event_payload, "tool_name", "name", "tool")
    if isinstance(value, str):
        return value
    tool_call = event_payload.get("tool_call")
    if isinstance(tool_call, dict) and isinstance(tool_call.get("name"), str):
        return str(tool_call["name"])
    return ""


def _profile_from_payload(payload: dict[str, Any]) -> str:
    value = payload.get("name")
    if isinstance(value, str):
        return value
    profile = payload.get("harness_profile")
    if isinstance(profile, dict) and isinstance(profile.get("name"), str):
        return str(profile["name"])
    return ""


def _contract_type_from_payload(payload: dict[str, Any]) -> str:
    value = payload.get("task_type")
    return str(value) if isinstance(value, str) else ""


def summarize_trace(trace: StoredRunTrace | None, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract the trace fields that are useful when comparing chat smoke runs."""
    fallback = fallback or {}
    if trace is None:
        return {
            "run_id": fallback.get("run_id"),
            "run_status": fallback.get("run_status") or "",
            "event_count": int(fallback.get("run_event_count") or 0),
            "profile": "",
            "contract": "",
            "completion_status": "",
            "completion_reason": "",
            "tool_count": int(fallback.get("tool_call_count") or 0),
            "tools": [],
            "failed_tool_count": 0,
            "failed_tools": [],
        }

    tools: list[str] = []
    failed_tools: list[str] = []
    profile = ""
    contract = ""
    completion_status = ""
    completion_reason = ""

    for event in trace.events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if event.event_type == "tool_started":
            tool_name = _tool_name_from_event(payload)
            if tool_name:
                tools.append(tool_name)
        elif event.event_type == "tool_result":
            ok = payload.get("ok")
            if ok is False:
                failed_tool = _tool_name_from_event(payload)
                if failed_tool:
                    failed_tools.append(failed_tool)
        elif event.event_type.startswith("harness_profile."):
            profile = _profile_from_payload(payload) or profile
        elif event.event_type == "task_contract.created":
            contract = _contract_type_from_payload(payload) or contract
        elif event.event_type.startswith("completion_gate"):
            completion_status = str(payload.get("status") or completion_status)
            completion_reason = str(payload.get("reason") or completion_reason)

    run = trace.run
    return {
        "run_id": run.run_id,
        "run_status": run.status,
        "event_count": len(trace.events),
        "part_count": len(trace.parts),
        "file_change_count": len(trace.file_changes),
        "profile": profile,
        "contract": contract,
        "completion_status": completion_status,
        "completion_reason": completion_reason,
        "tool_count": len(tools),
        "tools": tools,
        "failed_tool_count": len(failed_tools),
        "failed_tools": failed_tools,
    }


def check_trace(case: SmokeCase, trace_summary: dict[str, Any]) -> list[str]:
    """Return strict smoke failures for one case."""
    failures: list[str] = []
    tools = {str(tool) for tool in trace_summary.get("tools") or []}
    removed_tools = sorted(tools & REMOVED_TOOL_NAMES)
    if removed_tools:
        failures.append(f"removed tool appeared: {', '.join(removed_tools)}")

    web_tools = tools & WEB_TOOL_NAMES
    if case.expect_web_tools is True and not web_tools:
        failures.append("expected at least one web tool")
    elif case.expect_web_tools is False and web_tools:
        failures.append(f"unexpected web tool: {', '.join(sorted(web_tools))}")
    return failures


async def run_smoke_cases(
    cases: list[SmokeCase],
    *,
    gateway_url: str,
    ws_url: str | None,
    access_token: str | None,
    timeout_seconds: float,
    external_chat_prefix: str,
    db_path: str | Path | None,
    send_web_chat: SendWebChat = run_web_chat,
) -> dict[str, Any]:
    """Run all smoke cases through the Web gateway and inspect their stored traces."""
    storage = SQLiteStorage(db_path)
    started = time.monotonic()
    results: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        external_chat_id = f"{external_chat_prefix}-{index:02d}-{case.case_id}"
        payload = await send_web_chat(
            case.prompt,
            gateway_url=gateway_url,
            ws_url=ws_url,
            external_chat_id=external_chat_id,
            access_token=access_token,
            timeout_seconds=timeout_seconds,
        )
        session_id = str(payload.get("session_id") or f"web:{external_chat_id}")
        run_id = str(payload.get("run_id") or "")
        trace = await storage.get_run_trace(session_id, run_id) if run_id else None
        trace_summary = summarize_trace(trace, fallback=payload)
        failures = check_trace(case, trace_summary)
        results.append(
            {
                "case": case.case_id,
                "ok": not failures and bool(payload.get("ok", True)),
                "prompt": case.prompt,
                "session_id": session_id,
                "external_chat_id": external_chat_id,
                "reply_preview": str(payload.get("reply") or "")[:240],
                "elapsed_seconds": payload.get("elapsed_seconds"),
                "failures": failures,
                "trace": trace_summary,
            }
        )

    failed = [result for result in results if not result["ok"]]
    return {
        "ok": not failed,
        "case_count": len(results),
        "failed_count": len(failed),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "results": results,
    }


def select_cases(case_ids: list[str] | None = None) -> list[SmokeCase]:
    """Select smoke cases by id, preserving the default ordering."""
    if not case_ids:
        return list(DEFAULT_SMOKE_CASES)
    requested = set(case_ids)
    cases = [case for case in DEFAULT_SMOKE_CASES if case.case_id in requested]
    found = {case.case_id for case in cases}
    missing = sorted(requested - found)
    if missing:
        raise ValueError(f"Unknown smoke case(s): {', '.join(missing)}")
    return cases


def _render_text(payload: dict[str, Any]) -> None:
    typer.echo("OpenSprite CLI Chat Trace Smoke")
    typer.echo(f"Cases: {payload['case_count']} failed={payload['failed_count']} elapsed={payload['elapsed_seconds']}s")
    for result in payload["results"]:
        trace = result["trace"]
        status = "PASS" if result["ok"] else "FAIL"
        tools = ", ".join(trace.get("tools") or []) or "-"
        typer.echo(
            f"{status} {result['case']} run={trace.get('run_id') or '-'} "
            f"profile={trace.get('profile') or '-'} tools={tools}"
        )
        for failure in result.get("failures") or []:
            typer.echo(f"  - {failure}")


def chat_smoke_command(
    *,
    gateway_url: str,
    ws_url: str | None,
    access_token: str | None,
    timeout_seconds: float,
    external_chat_prefix: str,
    db_path: str | None,
    case_ids: list[str] | None,
    json_output: bool,
) -> None:
    """Run the Typer-facing chat trace smoke command."""
    try:
        cases = select_cases(case_ids)
        payload = asyncio.run(
            run_smoke_cases(
                cases,
                gateway_url=gateway_url,
                ws_url=ws_url,
                access_token=access_token,
                timeout_seconds=timeout_seconds,
                external_chat_prefix=external_chat_prefix,
                db_path=db_path,
            )
        )
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(_json_for_stdout(payload))
    else:
        _render_text(payload)
    if not payload["ok"]:
        raise typer.Exit(code=1)
