"""HTTP and SSE contract tests for the Agent chat router."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from opensprite_backend.application import AgentChatError, ChatErrorCode
from opensprite_backend.app import create_app
from opensprite_backend.conversations.models import (
    CompletionReason,
    ConversationPage,
    ConversationSummary,
    Message,
    MessagePage,
    PublicRunError,
    RunEvent,
    RunEventType,
    RunSnapshot,
    RunStatus,
    StartRunResult,
)


NOW = datetime(2026, 8, 21, 8, 30, tzinfo=UTC)
CONVERSATION_ID = "49d6c5e3-1724-44a7-9e69-0c0103176461"
RUN_ID = "e7527bf5-81c9-4534-908c-a9a9bc501f26"
USER_MESSAGE_ID = "c01956dc-fdf0-435c-a3be-e7eb5fd65f22"
ASSISTANT_MESSAGE_ID = "7e660e86-4838-4af5-99d5-ab926428b1c0"


def run_snapshot(status: RunStatus = RunStatus.QUEUED) -> RunSnapshot:
    return RunSnapshot(
        id=RUN_ID,
        conversation_id=CONVERSATION_ID,
        user_message_id=USER_MESSAGE_ID,
        assistant_message_id=(
            ASSISTANT_MESSAGE_ID if status is RunStatus.COMPLETED else None
        ),
        provider_id="openrouter",
        model_id="openrouter/auto",
        response_mode="default",
        status=status,
        error=None,
        partial_text="done" if status is RunStatus.COMPLETED else "",
        created_at=NOW,
        started_at=NOW if status is not RunStatus.QUEUED else None,
        finished_at=NOW if status is RunStatus.COMPLETED else None,
        completion_reason=(
            CompletionReason.STOP if status is RunStatus.COMPLETED else None
        ),
    )


class RecordingChat:
    def __init__(self) -> None:
        self.start_args: tuple[str | None, str, str] | None = None
        self.cancelled: str | None = None
        self.after_sequence: int | None = None
        self.failure: ChatErrorCode | None = None

    def fail_if_requested(self) -> None:
        if self.failure is not None:
            raise AgentChatError(self.failure)

    async def list_conversations(self, *, limit: int, before: str | None):
        self.fail_if_requested()
        assert limit == 50
        assert before is None
        return ConversationPage(
            items=(
                ConversationSummary(
                    id=CONVERSATION_ID,
                    title="整理今天的工作",
                    latest_message_preview="done",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ),
            next_cursor=None,
        )

    async def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
        before_sequence: int | None,
    ):
        self.fail_if_requested()
        assert conversation_id == CONVERSATION_ID
        assert limit == 100
        assert before_sequence is None
        return MessagePage(
            items=(
                Message(
                    id=USER_MESSAGE_ID,
                    conversation_id=CONVERSATION_ID,
                    run_id=RUN_ID,
                    role="user",
                    content="hello",
                    sequence=1,
                    created_at=NOW,
                ),
            ),
            next_before_sequence=None,
        )

    async def start_run(
        self,
        *,
        conversation_id: str | None,
        client_request_id: str,
        message: str,
    ):
        self.fail_if_requested()
        self.start_args = (conversation_id, client_request_id, message)
        return StartRunResult(
            conversation=ConversationSummary(
                id=CONVERSATION_ID,
                title="hello",
                latest_message_preview="hello",
                created_at=NOW,
                updated_at=NOW,
            ),
            run=run_snapshot(),
            replayed=False,
        )

    async def get_run(self, run_id: str):
        self.fail_if_requested()
        assert run_id == RUN_ID
        return run_snapshot(RunStatus.COMPLETED)

    async def cancel_run(self, run_id: str):
        self.fail_if_requested()
        self.cancelled = run_id
        return run_snapshot(RunStatus.CANCELLED)

    async def stream_events(self, run_id: str, *, after_sequence: int):
        self.fail_if_requested()
        assert run_id == RUN_ID
        self.after_sequence = after_sequence
        yield RunEvent(
            sequence=2,
            type=RunEventType.RUN_FAILED,
            run_id=RUN_ID,
            conversation_id=CONVERSATION_ID,
            created_at=NOW,
            data={
                "error": {
                    "code": "provider_timeout",
                    "message": "模型廠家回應逾時。",
                    "retryable": True,
                }
            },
        )


def client(chat: RecordingChat) -> TestClient:
    return TestClient(create_app(agent_chat=chat))


def test_conversation_and_run_json_shapes_match_contract() -> None:
    chat = RecordingChat()
    with client(chat) as browser:
        conversations = browser.get("/api/conversations")
        messages = browser.get(
            f"/api/conversations/{CONVERSATION_ID}/messages"
        )
        started = browser.post(
            "/api/runs",
            json={
                "conversationId": None,
                "clientRequestId": "ba66c043-6229-469c-84b1-36f617cfc328",
                "message": "hello",
            },
        )
        run = browser.get(f"/api/runs/{RUN_ID}")

    assert conversations.status_code == 200
    assert conversations.json() == {
        "conversations": [
            {
                "id": CONVERSATION_ID,
                "title": "整理今天的工作",
                "latestMessagePreview": "done",
                "createdAt": "2026-08-21T08:30:00Z",
                "updatedAt": "2026-08-21T08:30:00Z",
            }
        ],
        "nextCursor": None,
    }
    assert messages.status_code == 200
    assert messages.json()["messages"][0] == {
        "id": USER_MESSAGE_ID,
        "conversationId": CONVERSATION_ID,
        "runId": RUN_ID,
        "role": "user",
        "content": "hello",
        "sequence": 1,
        "createdAt": "2026-08-21T08:30:00Z",
    }
    assert started.status_code == 202
    assert started.json() == {
        "conversationId": CONVERSATION_ID,
        "runId": RUN_ID,
        "status": "queued",
    }
    assert chat.start_args == (
        None,
        "ba66c043-6229-469c-84b1-36f617cfc328",
        "hello",
    )
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert run.json()["completionReason"] == "stop"
    assert run.json()["providerId"] == "openrouter"
    assert run.json()["responseMode"] == "default"


def test_cancel_is_bodyless_and_returns_terminal_or_cancelling_status() -> None:
    chat = RecordingChat()
    with client(chat) as browser:
        invalid = browser.post(f"/api/runs/{RUN_ID}/cancel", content=b"{}")
        cancelled = browser.post(f"/api/runs/{RUN_ID}/cancel")

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_request"
    assert cancelled.status_code == 202
    assert cancelled.json() == {"runId": RUN_ID, "status": "cancelled"}
    assert chat.cancelled == RUN_ID


def test_sse_replays_after_last_event_id_with_safe_exact_frame() -> None:
    chat = RecordingChat()
    with client(chat) as browser:
        with browser.stream(
            "GET",
            f"/api/runs/{RUN_ID}/events",
            headers={"Last-Event-ID": "1"},
        ) as streamed:
            body = streamed.read().decode()

    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert streamed.headers["cache-control"] == "no-cache"
    assert chat.after_sequence == 1
    assert body == (
        "id: 2\n"
        "event: run.failed\n"
        "data: {\"sequence\":2,\"type\":\"run.failed\","
        f"\"runId\":\"{RUN_ID}\","
        f"\"conversationId\":\"{CONVERSATION_ID}\","
        "\"createdAt\":\"2026-08-21T08:30:00Z\","
        "\"data\":{\"error\":{\"code\":\"provider_timeout\","
        "\"message\":\"模型廠家回應逾時。\",\"retryable\":true}}}\n\n"
    )


def test_chat_errors_use_fixed_status_and_safe_envelope() -> None:
    chat = RecordingChat()
    cases = [
        (ChatErrorCode.NOT_FOUND, 404),
        (ChatErrorCode.RUN_BUSY, 409),
        (ChatErrorCode.DATABASE_UNAVAILABLE, 503),
    ]
    with client(chat) as browser:
        for code, status in cases:
            chat.failure = code
            response = browser.get(f"/api/runs/{RUN_ID}")
            assert response.status_code == status
            assert response.json()["error"]["code"] == code.value
            assert set(response.json()["error"]) == {
                "code",
                "message",
                "retryable",
            }


def test_chat_mutations_require_existing_exact_same_origin_policy() -> None:
    chat = RecordingChat()
    app = create_app(agent_chat=chat, enforce_local_security=True)
    payload = {
        "conversationId": None,
        "clientRequestId": "ba66c043-6229-469c-84b1-36f617cfc328",
        "message": "hello",
    }

    with TestClient(app, base_url="http://127.0.0.1:8765") as browser:
        missing = browser.post("/api/runs", json=payload)
        accepted = browser.post(
            "/api/runs",
            json=payload,
            headers={"Origin": "http://127.0.0.1:8765"},
        )

    assert missing.status_code == 400
    assert chat.start_args is not None
    assert accepted.status_code == 202


def test_generated_chat_schema_keeps_strict_request_and_sse_content_type() -> None:
    schema = create_app().openapi()
    start = schema["components"]["schemas"]["StartRunRequest"]

    assert start["additionalProperties"] is False
    assert start["required"] == [
        "conversationId",
        "clientRequestId",
        "message",
    ]
    assert set(start["properties"]) == {
        "conversationId",
        "clientRequestId",
        "message",
    }
    stream = schema["paths"]["/api/runs/{run_id}/events"]["get"]
    assert "text/event-stream" in stream["responses"]["200"]["content"]
    assert set(stream["responses"]) >= {"200", "400", "404", "500", "503"}
