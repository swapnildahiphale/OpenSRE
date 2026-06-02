#!/usr/bin/env python3
"""Get detailed information about a Kubernetes pod.

Usage:
    python describe_pod.py <pod-name> -n <namespace>
    python describe_pod.py <pod-name> -n <namespace> --cluster-id <id>

Examples:
    python describe_pod.py payment-7f8b9c6d5-x2k4m -n otel-demo
    python describe_pod.py payment-7f8b9c6d5-x2k4m -n production --cluster-id abc123
"""

import argparse
import json
import sys
from pathlib import Path

from k8s_gateway_client import add_cluster_id_arg, execute_command, is_gateway_mode
from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException


def get_k8s_client():
    """Get Kubernetes API client.

    Prefers in-cluster service account auth (correct RBAC identity)
    over kubeconfig (which may resolve to the EC2 node IAM identity).
    """
    in_cluster = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
    kubeconfig = Path.home() / ".kube" / "config"

    if in_cluster.exists():
        k8s_config.load_incluster_config()
        print("[k8s-auth] Using in-cluster service account", file=sys.stderr)
    elif kubeconfig.exists():
        k8s_config.load_kube_config()
        print("[k8s-auth] Using kubeconfig (fallback)", file=sys.stderr)
    else:
        print(
            "Error: Kubernetes not configured. No in-cluster token or ~/.kube/config.",
            file=sys.stderr,
        )
        sys.exit(1)

    return client.CoreV1Api()


def format_pod_detail(result: dict) -> None:
    """Print pod details in human-readable format."""
    print(f"Pod: {result.get('name', '-')}")
    print(f"Namespace: {result.get('namespace', '-')}")
    print(f"Status: {result.get('status', '-')}")
    print(f"Node: {result.get('node', '-')}")
    print()

    containers = result.get("containers", [])
    print("Containers:")
    for c in containers:
        status_icon = "+" if c.get("ready") else "-"
        print(f"  {status_icon} {c.get('name', '-')}")
        print(f"     Image: {c.get('image', '-')}")
        print(f"     Restarts: {c.get('restart_count', 0)}")
        if c.get("resources"):
            print(f"     Resources: {c['resources']}")
    print()

    conditions = result.get("conditions", [])
    print("Conditions:")
    for cond in conditions:
        status_icon = "+" if cond.get("status") == "True" else "-"
        print(f"  {status_icon} {cond.get('type', '-')}: {cond.get('status', '-')}")
        if cond.get("reason"):
            print(f"     Reason: {cond['reason']}")


def main():
    parser = argparse.ArgumentParser(description="Get detailed pod information")
    parser.add_argument("pod_name", help="Name of the pod")
    parser.add_argument(
        "-n", "--namespace", default="default", help="Kubernetes namespace"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    add_cluster_id_arg(parser)
    args = parser.parse_args()

    try:
        if is_gateway_mode(args.cluster_id):
            result = execute_command(
                args.cluster_id,
                "describe_pod",
                {"pod_name": args.pod_name, "namespace": args.namespace},
            )
        else:
            core_v1 = get_k8s_client()
            pod = core_v1.read_namespaced_pod(
                name=args.pod_name, namespace=args.namespace
            )

            containers = []
            for c in pod.spec.containers:
                container_status = next(
                    (
                        cs
                        for cs in (pod.status.container_statuses or [])
                        if cs.name == c.name
                    ),
                    None,
                )

                resources = {}
                if c.resources:
                    if c.resources.requests:
                        resources["requests"] = dict(c.resources.requests)
                    if c.resources.limits:
                        resources["limits"] = dict(c.resources.limits)

                containers.append(
                    {
                        "name": c.name,
                        "image": c.image,
                        "ready": container_status.ready if container_status else False,
                        "restart_count": (
                            container_status.restart_count if container_status else 0
                        ),
                        "resources": resources if resources else None,
                    }
                )

            conditions = []
            for cond in pod.status.conditions or []:
                conditions.append(
                    {
                        "type": cond.type,
                        "status": cond.status,
                        "reason": cond.reason,
                    }
                )

            result = {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "node": pod.spec.node_name,
                "containers": containers,
                "conditions": conditions,
            }

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            format_pod_detail(result)

    except ApiException as e:
        print(f"Error: Kubernetes API error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
