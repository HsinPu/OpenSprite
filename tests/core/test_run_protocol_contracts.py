from opensprite.core.contracts import run_events, run_lifecycle


def _public_string_constants(module) -> dict[str, str]:
    return {
        name: value
        for name, value in vars(module).items()
        if name.isupper() and isinstance(value, str)
    }


def _public_frozenset_constants(module) -> dict[str, frozenset[str]]:
    return {
        name: value
        for name, value in vars(module).items()
        if name.isupper() and isinstance(value, frozenset)
    }


def test_run_event_wire_values_are_stable():
    assert _public_string_constants(run_events) == {
        "AUDIO_INPUT_TRANSCRIBED_EVENT": "audio_input.transcribed",
        "BACKGROUND_PROCESS_COMPLETED_EVENT": "background_process.completed",
        "BACKGROUND_PROCESS_LOST_EVENT": "background_process.lost",
        "BACKGROUND_PROCESS_NOTIFICATION_FAILED_EVENT": "background_process.notification_failed",
        "BACKGROUND_PROCESS_NOTIFICATION_SENT_EVENT": "background_process.notification_sent",
        "BACKGROUND_PROCESS_STARTED_EVENT": "background_process.started",
        "CURATOR_COMPLETED_EVENT": "curator.completed",
        "CURATOR_FAILED_EVENT": "curator.failed",
        "CURATOR_JOB_COMPLETED_EVENT": "curator.job.completed",
        "CURATOR_JOB_FAILED_EVENT": "curator.job.failed",
        "CURATOR_JOB_SKIPPED_EVENT": "curator.job.skipped",
        "CURATOR_JOB_STARTED_EVENT": "curator.job.started",
        "CURATOR_STARTED_EVENT": "curator.started",
        "EXECUTION_STOPPED_EVENT": "execution.stopped",
        "FILE_CHANGED_EVENT": "file_changed",
        "FILE_REVERT_APPLIED_EVENT": "file_revert.applied",
        "FILE_REVERT_FAILED_EVENT": "file_revert.failed",
        "FILE_REVERT_PREVIEWED_EVENT": "file_revert.previewed",
        "FILE_REVERT_SKIPPED_EVENT": "file_revert.skipped",
        "HISTORY_LOADED_EVENT": "history.loaded",
        "INBOUND_MEDIA_EVENT_PREFIX": "inbound_media.",
        "INBOUND_MEDIA_PERSISTED_EVENT": "inbound_media.persisted",
        "LLM_EVENT_PREFIX": "llm_",
        "LLM_STATUS_EVENT": "llm_status",
        "MCP_CONNECTED_EVENT": "mcp.connected",
        "MCP_CONNECTION_FAILED_EVENT": "mcp.connection_failed",
        "MCP_TOOLS_SYNCED_EVENT": "mcp.tools_synced",
        "MESSAGE_PART_DELTA_EVENT": "message_part_delta",
        "PROMPT_BUILT_EVENT": "prompt.built",
        "PROMPT_TOKENS_ESTIMATED_EVENT": "prompt.tokens_estimated",
        "REASONING_DELTA_EVENT": "reasoning_delta",
        "RUN_EVENT_PREFIX": "run_",
        "RUN_PART_DELTA_EVENT": "run_part_delta",
        "SEARCH_INDEX_MESSAGE_FAILED_EVENT": "search_index.message_failed",
        "SUBAGENT_CANCELLED_EVENT": "subagent.cancelled",
        "SUBAGENT_COMPLETED_EVENT": "subagent.completed",
        "SUBAGENT_FAILED_EVENT": "subagent.failed",
        "SUBAGENT_GROUP_CANCELLED_EVENT": "subagent.group.cancelled",
        "SUBAGENT_GROUP_COMPLETED_EVENT": "subagent.group.completed",
        "SUBAGENT_GROUP_FAILED_EVENT": "subagent.group.failed",
        "SUBAGENT_GROUP_STARTED_EVENT": "subagent.group.started",
        "SUBAGENT_STARTED_EVENT": "subagent.started",
        "TOOL_EVENT_PREFIX": "tool_",
        "TOOL_INPUT_DELTA_EVENT": "tool_input_delta",
        "TOOL_RESULT_EVENT": "tool_result",
        "TOOL_STARTED_EVENT": "tool_started",
        "VERIFICATION_EVENT_PREFIX": "verification_",
        "VERIFICATION_NAME_METADATA_FIELD": "verification_name",
        "VERIFICATION_RESULT_EVENT": "verification_result",
        "VERIFICATION_STARTED_EVENT": "verification_started",
        "VERIFICATION_STATUS_METADATA_FIELD": "verification_status",
        "WORKFLOW_COMPLETED_EVENT": "workflow.completed",
        "WORKFLOW_FAILED_EVENT": "workflow.failed",
        "WORKFLOW_STARTED_EVENT": "workflow.started",
        "WORKFLOW_STEP_COMPLETED_EVENT": "workflow.step.completed",
        "WORKFLOW_STEP_FAILED_EVENT": "workflow.step.failed",
        "WORKFLOW_STEP_STARTED_EVENT": "workflow.step.started",
    }


def test_run_lifecycle_wire_values_are_stable():
    assert _public_string_constants(run_lifecycle) == {
        "RUN_CANCELLED_EVENT": "run_cancelled",
        "RUN_CANCELLED_STATUS": "cancelled",
        "RUN_CANCEL_REQUESTED_EVENT": "run_cancel_requested",
        "RUN_COMPLETED_STATUS": "completed",
        "RUN_FAILED_EVENT": "run_failed",
        "RUN_FINISHED_EVENT": "run_finished",
        "RUN_RUNNING_STATUS": "running",
        "RUN_STARTED_EVENT": "run_started",
        "RUN_STOPPED_STATUS": "stopped",
    }


def test_run_event_groups_are_stable_and_immutable():
    assert _public_frozenset_constants(run_events) == {
        "BACKGROUND_PROCESS_EVENTS": frozenset(
            {
                "background_process.started",
                "background_process.completed",
                "background_process.lost",
                "background_process.notification_sent",
                "background_process.notification_failed",
            }
        ),
        "CURATOR_EVENTS": frozenset(
            {"curator.started", "curator.completed", "curator.failed"}
        ),
        "CURATOR_JOB_EVENTS": frozenset(
            {
                "curator.job.started",
                "curator.job.completed",
                "curator.job.skipped",
                "curator.job.failed",
            }
        ),
        "CURATOR_RUNNING_EVENTS": frozenset(
            {"curator.started", "curator.job.started"}
        ),
        "SUBAGENT_CANCELLED_EVENTS": frozenset(
            {"subagent.cancelled", "subagent.group.cancelled"}
        ),
        "SUBAGENT_COMPLETED_EVENTS": frozenset(
            {"subagent.completed", "subagent.group.completed"}
        ),
        "SUBAGENT_EVENTS": frozenset(
            {
                "subagent.started",
                "subagent.completed",
                "subagent.failed",
                "subagent.cancelled",
            }
        ),
        "SUBAGENT_FAILED_EVENTS": frozenset(
            {"subagent.failed", "subagent.group.failed"}
        ),
        "SUBAGENT_GROUP_EVENTS": frozenset(
            {
                "subagent.group.started",
                "subagent.group.completed",
                "subagent.group.failed",
                "subagent.group.cancelled",
            }
        ),
        "SUBAGENT_STARTED_EVENTS": frozenset(
            {"subagent.started", "subagent.group.started"}
        ),
        "TERMINAL_WORKFLOW_EVENTS": frozenset(
            {"workflow.completed", "workflow.failed"}
        ),
        "TEXT_DELTA_EVENTS": frozenset({"run_part_delta", "message_part_delta"}),
        "TOOL_LIFECYCLE_EVENTS": frozenset({"tool_started", "tool_result"}),
        "VERIFICATION_EVENTS": frozenset(
            {"verification_started", "verification_result"}
        ),
        "WORKFLOW_COMPLETED_EVENTS": frozenset(
            {"workflow.completed", "workflow.step.completed"}
        ),
        "WORKFLOW_FAILED_EVENTS": frozenset(
            {"workflow.failed", "workflow.step.failed"}
        ),
        "WORKFLOW_RUNNING_EVENTS": frozenset(
            {"workflow.started", "workflow.step.started"}
        ),
    }


def test_run_lifecycle_groups_are_stable_and_immutable():
    assert _public_frozenset_constants(run_lifecycle) == {
        "ACTIVE_RUN_EVENTS": frozenset(
            {"run_started", "run_finished", "run_failed", "run_cancelled"}
        ),
        "TERMINAL_RUN_EVENTS": frozenset(
            {"run_finished", "run_failed", "run_cancelled"}
        ),
    }
