"""Coding agent node -- stub/placeholder (disabled).

TODO: Implement coding agent for automated remediation.
The graph edge is present but conditionally skipped.
"""

import logging

logger = logging.getLogger(__name__)


def coding(state: dict) -> dict:
    """Stub coding agent -- currently disabled.

    Will be implemented for automated remediation actions.
    """
    logger.info("[CODING] Coding agent is disabled -- skipping")
    return {}
