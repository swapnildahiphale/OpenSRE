"""Teams SDK entrypoint for OpenSRE teams-bot."""

import asyncio
import logging
import sys

from bot_handlers import register_handlers
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    cfg = Config()
    if not cfg.is_configured():
        logger.warning(
            "TEAMS_APP_ID / TEAMS_APP_PASSWORD / TEAMS_TENANT_ID not fully set — "
            "teams-bot exiting cleanly"
        )
        sys.exit(0)

    from microsoft_teams.apps import App

    app = App()
    register_handlers(app)
    logger.info("Starting OpenSRE teams-bot on port %s", cfg.PORT)
    # App.start reads PORT / CLIENT_* from environment
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
