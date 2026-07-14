from opensprite.agent.turn_input import metadata_is_cli_via_web


def test_turn_metadata_helpers_normalize_marker_values():
    assert metadata_is_cli_via_web({"source": " cli_via_web "}) is True
    assert metadata_is_cli_via_web({"source": "browser"}) is False
