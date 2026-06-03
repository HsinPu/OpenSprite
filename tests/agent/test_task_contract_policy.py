from opensprite.agent.task_contract import _ensure_task_type_tool_groups, _normalize_planner_tool_groups


def test_planner_tool_group_aliases_are_normalized_without_duplicates():
    groups = _normalize_planner_tool_groups(["workspace_change", "workspace_write", "media_analysis", "ops", "unknown"])

    assert groups == ["workspace_write", "media", "verification"]


def test_task_type_required_tool_groups_are_added_from_policy_map():
    groups = ["workspace_write"]

    _ensure_task_type_tool_groups("code_change", groups)

    assert groups == ["workspace_write", "workspace_read"]


def test_task_type_required_tool_groups_preserve_existing_order_for_unknown_task_type():
    groups = ["execution"]

    _ensure_task_type_tool_groups("operations", groups)

    assert groups == ["execution"]
