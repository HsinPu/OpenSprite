from opensprite.agent.work_progress_action_policy import (
    NEXT_ACTION_ADDRESS_REVIEW_FINDINGS,
    NEXT_ACTION_COLLECT_REVIEW_EVIDENCE,
    NEXT_ACTION_CONTINUE_REVIEW,
    NEXT_ACTION_CONTINUE_VERIFICATION,
    NEXT_ACTION_CONTINUE_WORK,
    is_continue_work_next_action,
    is_review_follow_up_next_action,
    is_review_phase_next_action,
    is_verification_next_action,
)


def test_work_progress_action_policy_classifies_core_next_actions():
    assert is_verification_next_action(NEXT_ACTION_CONTINUE_VERIFICATION) is True
    assert is_verification_next_action(NEXT_ACTION_CONTINUE_WORK) is False
    assert is_continue_work_next_action(NEXT_ACTION_CONTINUE_WORK) is True
    assert is_continue_work_next_action(NEXT_ACTION_CONTINUE_VERIFICATION) is False


def test_work_progress_action_policy_distinguishes_review_phase_and_follow_up_actions():
    assert is_review_follow_up_next_action(NEXT_ACTION_COLLECT_REVIEW_EVIDENCE) is True
    assert is_review_follow_up_next_action(NEXT_ACTION_ADDRESS_REVIEW_FINDINGS) is True
    assert is_review_follow_up_next_action(NEXT_ACTION_CONTINUE_REVIEW) is False

    assert is_review_phase_next_action(NEXT_ACTION_COLLECT_REVIEW_EVIDENCE) is True
    assert is_review_phase_next_action(NEXT_ACTION_ADDRESS_REVIEW_FINDINGS) is True
    assert is_review_phase_next_action(NEXT_ACTION_CONTINUE_REVIEW) is True
    assert is_review_phase_next_action(NEXT_ACTION_CONTINUE_WORK) is False
