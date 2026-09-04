# teams-bot/config.py
"""Environment-backed configuration for the Teams bot."""

import os

from dotenv import load_dotenv

load_dotenv()


def _export_sdk_env(app_id: str, password: str, tenant_id: str) -> None:
    """Map OpenSRE TEAMS_* names to Teams SDK CLIENT_* env vars."""
    if app_id:
        os.environ.setdefault("CLIENT_ID", app_id)
    if password:
        os.environ.setdefault("CLIENT_SECRET", password)
    if tenant_id:
        os.environ.setdefault("TENANT_ID", tenant_id)


class Config:
    PORT = int(os.environ.get("PORT", "3978"))

    TEAMS_APP_ID = os.environ.get("TEAMS_APP_ID", "")
    TEAMS_APP_PASSWORD = os.environ.get("TEAMS_APP_PASSWORD", "")
    TEAMS_TENANT_ID = os.environ.get("TEAMS_TENANT_ID", "")

    SRE_AGENT_URL = os.environ.get("SRE_AGENT_URL", "http://localhost:8000")
    INVESTIGATE_AUTH_TOKEN = os.environ.get("INVESTIGATE_AUTH_TOKEN", "")
    WEB_UI_PUBLIC_BASE_URL = os.environ.get("WEB_UI_PUBLIC_BASE_URL", "")

    def __init__(self) -> None:
        _export_sdk_env(
            self.TEAMS_APP_ID, self.TEAMS_APP_PASSWORD, self.TEAMS_TENANT_ID
        )

    def is_configured(self) -> bool:
        return bool(
            self.TEAMS_APP_ID and self.TEAMS_APP_PASSWORD and self.TEAMS_TENANT_ID
        )
