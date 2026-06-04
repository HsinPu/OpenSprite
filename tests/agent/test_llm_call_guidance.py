from opensprite.agent.llm_call import _format_acceptance_criterion
from opensprite.agent.task_contract import (
    AcceptanceCriterion,
    ITEMIZED_OUTPUT_CRITERION_KIND,
    SOURCE_ARTIFACT_CRITERION_KIND,
    SOURCE_REFERENCE_CRITERION_KIND,
    VERIFICATION_OR_GAP_CRITERION_KIND,
)


def test_format_acceptance_criterion_uses_policy_helpers():
    assert "itemized result entries" in _format_acceptance_criterion(
        AcceptanceCriterion(kind=ITEMIZED_OUTPUT_CRITERION_KIND, min_count=3)
    )
    assert "traceable source" in _format_acceptance_criterion(
        AcceptanceCriterion(kind=SOURCE_ARTIFACT_CRITERION_KIND, min_count=2)
    )
    assert "gathered source" in _format_acceptance_criterion(
        AcceptanceCriterion(kind=SOURCE_REFERENCE_CRITERION_KIND)
    )
    assert "verification gap" in _format_acceptance_criterion(
        AcceptanceCriterion(kind=VERIFICATION_OR_GAP_CRITERION_KIND)
    )
