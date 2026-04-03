#!/usr/bin/env python3
"""Populate Neo4j with otel-demo K8s cluster topology and service dependencies."""

import os
import sys

from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "localdev")


def run_cypher_file(driver, filepath):
    """Parse and execute Cypher statements from a .cypher file."""
    with open(filepath) as f:
        content = f.read()

    # Split on semicolons, skip comments and empty statements
    statements = []
    for raw in content.split(";"):
        lines = []
        for line in raw.strip().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("//"):
                lines.append(line)
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)

    print(f"Parsed {len(statements)} Cypher statements from {filepath}")

    with driver.session() as session:
        for i, stmt in enumerate(statements):
            try:
                result = session.run(stmt)
                summary = result.consume()
                created = summary.counters.nodes_created
                rels = summary.counters.relationships_created
                deleted = summary.counters.nodes_deleted
                indexes = summary.counters.indexes_added
                if created or rels or deleted or indexes:
                    print(
                        f"  [{i+1}/{len(statements)}] +{created} nodes, +{rels} rels, -{deleted} deleted, +{indexes} indexes"
                    )
            except Exception as e:
                # Truncate statement for display
                preview = stmt[:80].replace("\n", " ")
                print(
                    f"  [{i+1}/{len(statements)}] ERROR: {e}\n    Statement: {preview}..."
                )
                # Continue — don't fail on index-already-exists etc.

    print("\nDone!")


def verify(driver):
    """Print summary stats from the graph."""
    with driver.session() as session:
        # Node counts by label
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
        )
        print("\n=== Graph Summary ===")
        total_nodes = 0
        for record in result:
            print(f"  {record['label']}: {record['count']}")
            total_nodes += record["count"]

        # Relationship counts by type
        result = session.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC"
        )
        total_rels = 0
        print()
        for record in result:
            print(f"  {record['type']}: {record['count']}")
            total_rels += record["count"]

        print(f"\nTotal: {total_nodes} nodes, {total_rels} relationships")

        # Sample dependency query
        print("\n=== Sample: cartservice blast radius ===")
        result = session.run("""
            MATCH (d:KubernetesDeployment {name: 'otel-demo-cartservice'})<-[:DEPENDS_ON]-(upstream)
            RETURN upstream.name AS service
        """)
        for record in result:
            print(f"  <- {record['service']}")

        result = session.run("""
            MATCH (d:KubernetesDeployment {name: 'otel-demo-cartservice'})-[:DEPENDS_ON]->(downstream)
            RETURN downstream.name AS service
        """)
        for record in result:
            print(f"  -> {record['service']}")


if __name__ == "__main__":
    cypher_file = os.path.join(os.path.dirname(__file__), "populate_neo4j.cypher")
    if not os.path.exists(cypher_file):
        print(f"ERROR: {cypher_file} not found")
        sys.exit(1)

    print(f"Connecting to Neo4j at {NEO4J_URI}")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    try:
        driver.verify_connectivity()
        print("Connected successfully\n")
        run_cypher_file(driver, cypher_file)
        verify(driver)
    finally:
        driver.close()
