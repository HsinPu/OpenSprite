from opensprite.app.agent.delegation_contracts import StoredDelegatedTask, selected_delegated_task


def test_stored_delegated_task_payload_preserves_api_shape():
    task = StoredDelegatedTask(
        task_id="task-1",
        prompt_type="explorer",
        status="completed",
        selected=True,
        summary="done",
        error="",
        child_session_id="session-child",
        last_child_run_id="run-child",
        metadata={"source": "delegate"},
        created_at=10.0,
        updated_at=20.0,
    )

    assert task.to_payload() == {
        "task_id": "task-1",
        "prompt_type": "explorer",
        "status": "completed",
        "selected": True,
        "summary": "done",
        "error": "",
        "child_session_id": "session-child",
        "last_child_run_id": "run-child",
        "metadata": {"source": "delegate"},
        "created_at": 10.0,
        "updated_at": 20.0,
    }


def test_selected_delegated_task_returns_first_selected_task():
    first = StoredDelegatedTask(task_id="first", selected=True)
    second = StoredDelegatedTask(task_id="second", selected=True)

    assert selected_delegated_task((first, second)) is first
    assert selected_delegated_task((StoredDelegatedTask(task_id="none"),)) is None
