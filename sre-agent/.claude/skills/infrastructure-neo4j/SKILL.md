---
name: infrastructure-neo4j
description: Query the OpenSRE knowledge graph for service topology, dependencies, and blast radius. Use after you identify an affected service or deployment — not on vague initial alerts alone.
allowed-tools: Bash(python *)
---

# infrastructure-neo4j

Query the OpenSRE knowledge graph (Neo4j) for service topology, dependencies, and blast radius.

## When to use

Use **after** you know which service or deployment is affected:

- Alert or ticket names a service (checkout, payments, surveys build target)
- Logs or metrics identify a failing deployment
- You need blast radius — what depends on this service, what it depends on

**Do not** query on vague tickets alone (e.g. "build pipeline failing" with no service). Gather evidence first, then query with the service name.

## Usage

```bash
python .claude/skills/infrastructure-neo4j/scripts/topology_search.py \
  --service checkout
```

## JSON output

```json
{
  "success": true,
  "result": {
    "service": "checkout",
    "resolved_name": "otel-demo-checkoutservice",
    "deployment": { "namespace": "...", "replicas": 1 },
    "upstream_dependents": [{ "service": "...", "via": "..." }],
    "downstream_dependencies": [{ "service": "...", "via": "..." }],
    "blast_radius": {
      "upstream_count": 2,
      "downstream_count": 3,
      "affected_services": ["frontend", "loadgenerator"]
    }
  }
}
```

On failure, `success` is `false` and `error` describes the problem. Failures are non-blocking — continue the investigation.

## Methodology

1. **After scoping** — once you have a service name, query topology before deep log dives when dependencies matter.
2. **Blast radius** — check `upstream_dependents` and `affected_services` when assessing impact.
3. **Root cause correlation** — shared upstream dependencies across multiple affected services suggest a common cause.

## Advanced (direct CLI)

For K8s status or custom Cypher when the script is insufficient:

```bash
python tools/neo4j_semantic_layer.py --action k8s-status --service <name>
python tools/neo4j_semantic_layer.py --action cypher --query "MATCH (s:Service) RETURN s.name LIMIT 10"
```
