from opensprite.agent.active_task_open_questions import clear_open_questions, normalize_open_questions


def test_clear_open_questions_returns_sentinel_list():
    assert clear_open_questions() == ["none"]


def test_normalize_open_questions_trims_and_preserves_questions():
    assert normalize_open_questions([" first ", "", "second"]) == ["first", "second"]


def test_normalize_open_questions_accepts_clear_sentinel():
    assert normalize_open_questions(["blocked", "NONE"]) == ["none"]
