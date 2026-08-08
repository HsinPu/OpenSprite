import re

from opensprite.core.contracts.subagents import SUBAGENT_TASK_ID_PATTERN


def test_subagent_task_id_pattern_preserves_supported_identifier_shape():
    pattern = re.compile(SUBAGENT_TASK_ID_PATTERN)

    assert pattern.fullmatch("task_abcdefgh") is not None
    assert pattern.fullmatch(f"task_{'a' * 64}") is not None
    assert pattern.fullmatch("task_abcd-1234_test") is not None
    assert pattern.fullmatch("task_short") is None
    assert pattern.fullmatch(f"task_{'a' * 65}") is None
    assert pattern.fullmatch("task_invalid.value") is None
    assert pattern.fullmatch("job_abcdefgh") is None
