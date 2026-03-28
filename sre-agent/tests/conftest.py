"""Shared fixtures and path setup for LangGraph migration tests."""

import os
import sys

# Add sre-agent root to sys.path so imports like `from state import ...` work
SRE_AGENT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SRE_AGENT_ROOT not in sys.path:
    sys.path.insert(0, SRE_AGENT_ROOT)
