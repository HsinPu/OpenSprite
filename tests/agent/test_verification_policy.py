from opensprite.agent.verification_policy import REQUIRED_VERIFICATION_FAILED_REASON


def test_required_verification_failed_reason_is_stable():
    assert REQUIRED_VERIFICATION_FAILED_REASON == "required verification did not pass"
