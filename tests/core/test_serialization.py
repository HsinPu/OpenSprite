from opensprite.core.serialization import json_safe_payload, json_safe_value


class _StringOnly:
    def __str__(self) -> str:
        return "string-value"


def test_json_safe_value_converts_nested_values_to_json_primitives():
    assert json_safe_value(
        {
            7: ("value", _StringOnly()),
            "nested": [{"enabled": True}],
        }
    ) == {
        "7": ["value", "string-value"],
        "nested": [{"enabled": True}],
    }


def test_json_safe_payload_normalizes_empty_and_nested_payloads():
    assert json_safe_payload(None) == {}
    assert json_safe_payload({}) == {}
    assert json_safe_payload({"items": (1, 2)}) == {"items": [1, 2]}
