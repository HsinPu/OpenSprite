from opensprite.agent.task_context_policy import task_text_tokens


def test_task_text_tokens_supports_latin_and_cjk_follow_up_text():
    assert task_text_tokens("and this one?") == ("and", "this", "one")
    assert task_text_tokens("那00981t呢") == ("那00981t呢",)
