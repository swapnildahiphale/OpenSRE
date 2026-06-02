---
name: infrastructure-kubernetes
description: Kubernetes debugging methodology and scripts. Use for pod crashes, CrashLoopBackOff, OOMKilled, deployment issues, resource problems, or container failures.
---

# Kubernetes Debugging

## Core Principle: Events Before Logs

**ALWAYS check pod events BEFORE logs.** Events explain 80% of issues faster:
- OOMKilled -> Memory limit exceeded
- ImagePullBackOff -> Image not found or auth issue
- FailedScheduling -> No nodes with enough resources
- CrashLoopBackOff -> Container crashing repeatedly

## Access Mode

Scripts support two modes. Try **direct mode first** (no --cluster-id), then gateway if direct fails.

### Direct mode (kubectl / kubeconfig)
Run scripts WITHOUT --cluster-id. They use the local kubeconfig (~/.kube/config) or in-cluster service account.
```bash
python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n otel-demo
python .claude/skills/infrastructure-kubernetes/scripts/get_events.py <pod-name> -n otel-demo
python .claude/skills/infrastructure-kubernetes/scripts/get_logs.py <pod-name> -n otel-demo --tail 100
```

You can also run kubectl directly if the scripts don't cover your use case:
```bash
kubectl get pods -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl logs -n <namespace> <pod-name> --tail=100
kubectl describe pod -n <namespace> <pod-name>
```

### Gateway mode (remote clusters via k8s-gateway)
Only if `K8S_GATEWAY_URL` is configured and clusters are registered. Use --cluster-id.
```bash
python .claude/skills/infrastructure-kubernetes/scripts/list_clusters.py
python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n production --cluster-id <CLUSTER_ID>
```

## Available Scripts

All scripts are in `.claude/skills/infrastructure-kubernetes/scripts/`

### list_pods.py - List pods with status
```bash
python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n <namespace> [--label <selector>]
```

### get_events.py - Get pod events (USE FIRST!)
```bash
python .claude/skills/infrastructure-kubernetes/scripts/get_events.py <pod-name> -n <namespace>
```

### get_logs.py - Get pod logs
```bash
python .claude/skills/infrastructure-kubernetes/scripts/get_logs.py <pod-name> -n <namespace> [--tail N] [--container NAME]
```

### describe_pod.py - Detailed pod info
```bash
python .claude/skills/infrastructure-kubernetes/scripts/describe_pod.py <pod-name> -n <namespace>
```

### describe_deployment.py - Deployment status and rollout history
```bash
python .claude/skills/infrastructure-kubernetes/scripts/describe_deployment.py <deployment-name> -n <namespace>
```

### list_namespaces.py - List all namespaces
```bash
python .claude/skills/infrastructure-kubernetes/scripts/list_namespaces.py
```

### get_resources.py - Resource usage vs limits
```bash
python .claude/skills/infrastructure-kubernetes/scripts/get_resources.py <pod-name> -n <namespace>
```

### describe_node.py - Node status, conditions, and resource usage
```bash
python .claude/skills/infrastructure-kubernetes/scripts/describe_node.py <node-name>
python .claude/skills/infrastructure-kubernetes/scripts/describe_node.py --all
```

## Debugging Workflows

### Pod Not Starting (Pending/CrashLoopBackOff)
1. `list_pods.py` - Check pod status
2. `get_events.py` - Look for scheduling/pull/crash events
3. `describe_pod.py` - Check conditions and container states
4. `get_logs.py` - Only if events don't explain

### Pod Restarting (OOMKilled/Crashes)
1. `get_events.py` - Check for OOMKilled or error events
2. `get_resources.py` - Compare usage vs limits
3. `get_logs.py` - Check for errors before crash
4. `describe_pod.py` - Check restart count and state

### Deployment Not Progressing
1. `describe_deployment.py` - Check replica counts and rollout history
2. `list_pods.py` - Find stuck pods
3. `get_events.py` - Check events on stuck pods

### Node Resource Issues
1. `describe_node.py --all` - Check all nodes
2. `list_pods.py` - Check for Pending pods
3. `get_events.py` - Look for FailedScheduling

## Common Issues & Solutions

| Event Reason | Meaning | Action |
|--------------|---------|--------|
| OOMKilled | Container exceeded memory limit | Increase limits or fix memory leak |
| ImagePullBackOff | Can't pull image | Check image name, registry auth |
| CrashLoopBackOff | Container keeps crashing | Check logs for startup errors |
| FailedScheduling | No node can run pod | Check node resources, taints |
| Unhealthy | Liveness probe failed | Check probe config, app health |

## Output Format

When reporting findings, use this structure:

```
## Kubernetes Analysis

**Pod**: <name>
**Namespace**: <namespace>
**Status**: <phase> (Restarts: N)

### Events
- [timestamp] <reason>: <message>

### Issues Found
1. [Issue description with evidence]

### Root Cause Hypothesis
[Based on events and logs]

### Recommended Action
[Specific remediation step]
```
