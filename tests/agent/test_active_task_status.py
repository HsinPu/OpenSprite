from opensprite.agent.active_task_status import active_task_status, has_current_active_task


def test_active_task_status_parses_rendered_status_line():
    block = "- Goal: Demo\n- Status: waiting_user\n- Current step: inspect"

    assert active_task_status(block) == "waiting_user"
    assert has_current_active_task(block) is True


def test_active_task_status_defaults_to_inactive():
    assert active_task_status("- Goal: Demo") == "inactive"
    assert has_current_active_task("- Status: done") is False

