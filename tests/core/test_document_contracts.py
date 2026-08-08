from typing import Protocol, get_type_hints

from opensprite.core.contracts.documents import CuratorTurnResult


def test_curator_turn_result_contract_preserves_required_fields():
    assert Protocol in CuratorTurnResult.__mro__
    assert get_type_hints(CuratorTurnResult) == {
        "executed_tool_calls": int,
        "used_configure_skill": bool,
    }
