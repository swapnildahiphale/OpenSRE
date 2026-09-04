"""Build OpenSRE web UI links for Teams final replies."""

VIEW_LINK_LABEL = "View in OpenSRE"


def build_agent_run_url(base_url: str, run_id: str) -> str | None:
    """Return the team console run URL, or None when inputs are missing."""
    base = (base_url or "").strip().rstrip("/")
    rid = (run_id or "").strip()
    if not base or not rid:
        return None
    return f"{base}/team/agent-runs/{rid}"


def format_view_link_markdown(url: str) -> str:
    return f"[{VIEW_LINK_LABEL}]({url})"
