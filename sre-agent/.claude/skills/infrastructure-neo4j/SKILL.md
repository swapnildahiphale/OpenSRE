# Infrastructure Knowledge Graph (Neo4j)

## When to use
- Before starting an investigation, to understand the service topology
- When you need to know what depends on a service (blast radius analysis)
- When you need Kubernetes status of a service (pods, deployments, replicas)
- When you need to understand the relationship between services

## How to use

### Get service topology
```bash
python /app/tools/neo4j_semantic_layer.py --action service-info --service <service-name>
```

### Get Kubernetes status
```bash
python /app/tools/neo4j_semantic_layer.py --action k8s-status --service <service-name>
```

### Get service relationships
```bash
python /app/tools/neo4j_semantic_layer.py --action relationships --service <service-name>
```

### Run custom Cypher query
```bash
python /app/tools/neo4j_semantic_layer.py --action cypher --query "MATCH (s:Service) RETURN s.name LIMIT 10"
```

## Methodology

1. **Pre-investigation context**: Before analyzing logs or metrics, query the KG to understand:
   - What the service does
   - What depends on it (downstream impact)
   - What it depends on (upstream causes)
   - Current K8s health status

2. **Blast radius analysis**: When a service is affected:
   - Query all downstream dependencies
   - Check if downstream services also show errors
   - Report the full blast radius

3. **Root cause correlation**: When multiple services are affected:
   - Query the topology to find common upstream dependencies
   - The shared dependency is likely the root cause
