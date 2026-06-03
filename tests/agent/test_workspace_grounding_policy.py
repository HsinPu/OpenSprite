from opensprite.agent.workspace_grounding_policy import contains_workspace_location_clue


def test_workspace_location_clue_accepts_path_supplied_by_caller():
    assert contains_workspace_location_clue("the answer names a path", has_workspace_path=True) is True


def test_workspace_location_clue_accepts_symbol_or_quoted_code_token():
    assert contains_workspace_location_clue("function load_config handles it") is True
    assert contains_workspace_location_clue("check `AuthSettings`") is True


def test_workspace_location_clue_rejects_generic_answer():
    assert contains_workspace_location_clue("it is configured in the project") is False
