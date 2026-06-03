from opensprite.agent.web_source_policy import web_source_has_substantive_detail


def test_web_source_has_substantive_detail_accepts_good_fetch_source():
    assert web_source_has_substantive_detail(
        {
            "tool_name": "web_fetch",
            "has_main_content": True,
            "is_too_short": False,
            "blocked_or_challenge": False,
            "content_chars": 1200,
            "min_content_chars": 800,
        }
    )


def test_web_source_has_substantive_detail_rejects_blocked_or_short_fetch_source():
    assert not web_source_has_substantive_detail({"tool_name": "web_fetch", "blocked_or_challenge": True})
    assert not web_source_has_substantive_detail({"tool_name": "web_fetch", "is_too_short": True})
    assert not web_source_has_substantive_detail(
        {"tool_name": "web_fetch", "has_main_content": True, "content_chars": 120, "min_content_chars": 800}
    )


def test_web_source_has_substantive_detail_requires_fetched_source_tool():
    assert not web_source_has_substantive_detail({"tool_name": "web_search", "content_chars": 1200})
