from run_links import build_agent_run_url, format_view_link_markdown


def test_build_agent_run_url():
    assert build_agent_run_url("https://opensre.example.com", "abc123") == (
        "https://opensre.example.com/team/agent-runs/abc123"
    )


def test_build_agent_run_url_strips_trailing_slash():
    assert build_agent_run_url("https://opensre.example.com/", "abc123") == (
        "https://opensre.example.com/team/agent-runs/abc123"
    )


def test_build_agent_run_url_missing_inputs():
    assert build_agent_run_url("", "abc") is None
    assert build_agent_run_url("https://x.com", "") is None


def test_format_view_link_markdown():
    assert format_view_link_markdown("https://x.com/r") == (
        "[View in OpenSRE](https://x.com/r)"
    )
