"""Shared Neo4j driver for episodic memory and topology KG (singleton).

Connection settings: repo-root `.env` (NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_URI, …).
Docker Compose overrides NEO4J_URI to bolt://neo4j:7687 inside the sre-agent container.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

# Load repo-root .env when running sre-agent on the host (pytest, scripts, uv run).
for _parent in Path(__file__).resolve().parents:
    _env = _parent / ".env"
    if _env.is_file():
        load_dotenv(_env)
        break
else:
    load_dotenv()

logger = logging.getLogger(__name__)

# Host default uses compose-published bolt port (7688). In-container URI is set by compose.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "localdev")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

_driver: Optional[Driver] = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        logger.info("[MEMORY] Neo4j driver initialized: %s", NEO4J_URI)
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
