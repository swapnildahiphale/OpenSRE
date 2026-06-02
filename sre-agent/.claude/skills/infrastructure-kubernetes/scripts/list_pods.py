#!/usr/bin/env python3
"""List pods in a Kubernetes namespace with their status.

Usage:
    python list_pods.py -n <namespace> [--label <selector>]
    python list_pods.py -n <namespace> --cluster-id <id>

Examples:
    python list_pods.py -n otel-demo
    python list_pods.py -n otel-demo --label app.kubernetes.io/name=payment
    python list_pods.py -n production --cluster-id abc123
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


def format_pods_table(namespace: str, pod_list: list[dict]) -> None:
    """Print pods as a human-readable table."""
    print(f"Namespace: {namespace}")
    print(f"Pod count: {len(pod_list)}")
    print()
    print(f"{'NAME':<50} {'STATUS':<12} {'READY':<8} {'RESTARTS':<10}")
    print("-" * 80)
    for pod in pod_list:
        print(
            f"{pod['name']:<50} {pod.get('status', '-'):<12} "
            f"{pod.get('ready', '-'):<8} {pod.get('restarts', 0):<10}"
        )


def main():
    parser = argparse.ArgumentParser(description="List pods in a Kubernetes namespace")
    parser.add_argument(
        "-n", "--namespace", default="default", help="Kubernetes namespace"
    )
    parser.add_argument(
        "--label", dest="label_selector", help="Label selector (e.g., app=myapp)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    add_cluster_id_arg(parser)
    args = parser.parse_args()

    try:
        if is_gateway_mode(args.cluster_id):
            params = {"namespace": args.namespace}
            if args.label_selector:
                params["label_selector"] = args.label_selector
            result = execute_command(args.cluster_id, "list_pods", params)
            pod_list = result.get("pods", [])
        else:
            core_v1 = get_k8s_client()
            pods = core_v1.list_namespaced_pod(
                namespace=args.namespace,
                label_selector=args.label_selector,
            )

            pod_list = []
            for pod in pods.items:
                ready_count = sum(
                    1 for cs in (pod.status.container_statuses or []) if cs.ready
                )
                total_count = len(pod.spec.containers)
                restart_count = sum(
                    cs.restart_count for cs in (pod.status.container_statuses or [])
                )

                pod_list.append(
                    {
                        "name": pod.metadata.name,
                        "status": pod.status.phase,
                        "ready": f"{ready_count}/{total_count}",
                        "restarts": restart_count,
                        "age": str(pod.metadata.creation_timestamp),
                    }
                )

        if args.json:
            print(json.dumps({"namespace": args.namespace, "pods": pod_list}, indent=2))
        else:
            format_pods_table(args.namespace, pod_list)

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
