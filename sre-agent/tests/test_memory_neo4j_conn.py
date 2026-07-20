import os

import pytest

neo4j = pytest.importorskip("neo4j")
pytestmark = pytest.mark.skipif(
    not os.getenv("NEO4J_URI"), reason="NEO4J_URI not set; integration test"
)


def test_get_driver_connects_and_runs_query():
    from memory.neo4j_conn import NEO4J_DATABASE, get_driver

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        val = s.run("RETURN 1 AS n").single()["n"]
    assert val == 1


def test_get_driver_is_singleton():
    from memory.neo4j_conn import get_driver

    assert get_driver() is get_driver()
