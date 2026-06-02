#!/usr/bin/env python3
"""List all namespaces in a Kubernetes cluster.

Supports both direct K8s API access and remote access via k8s-gateway.

Usage:
    python list_namespaces.py
    python list_namespaces.py --cluster-id <id>
    python list_namespaces.py --json
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
    """Get Kubernetes API client."""
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


def main():
    parser = argparse.ArgumentParser(description="List Kubernetes namespaces")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    add_cluster_id_arg(parser)
    args = parser.parse_args()

    try:
        if is_gateway_mode(args.cluster_id):
            result = execute_command(args.cluster_id, "list_namespaces", {})
        else:
            core_v1 = get_k8s_client()
            namespaces = core_v1.list_namespace()
            result = {
                "namespace_count": len(namespaces.items),
                "namespaces": [
                    {
                        "name": ns.metadata.name,
                        "status": ns.status.phase,
                        "created_at": str(ns.metadata.creation_timestamp),
                    }
                    for ns in namespaces.items
                ],
            }

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Namespace count: {result['namespace_count']}")
            print()
            print(f"{'NAME':<40} {'STATUS':<12}")
            print("-" * 52)
            for ns in result["namespaces"]:
                print(f"{ns['name']:<40} {ns.get('status', '-'):<12}")

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
