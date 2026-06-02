#!/usr/bin/env python3
"""Get events related to a Kubernetes pod.

ALWAYS check events BEFORE logs - events explain most issues faster.
Common events: OOMKilled, ImagePullBackOff, FailedScheduling, CrashLoopBackOff

Usage:
    python get_events.py <pod-name> -n <namespace>
    python get_events.py <pod-name> -n <namespace> --cluster-id <id>

Examples:
    python get_events.py payment-7f8b9c6d5-x2k4m -n otel-demo
    python get_events.py payment-7f8b9c6d5-x2k4m -n production --cluster-id abc123
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


def format_events(pod_name: str, namespace: str, event_list: list[dict]) -> None:
    """Print events in human-readable format."""
    print(f"Pod: {pod_name}")
    print(f"Namespace: {namespace}")
    print(f"Event count: {len(event_list)}")
    print()

    if not event_list:
        print("No events found for this pod.")
    else:
        for event in event_list:
            event_type = "⚠️" if event["type"] == "Warning" else "ℹ️"
            print(
                f"{event_type} [{event.get('last_timestamp', '-')}] "
                f"{event.get('reason', '-')}: {event.get('message', '-')}"
            )
            if event.get("count") and event["count"] > 1:
                print(f"   (occurred {event['count']} times)")
            print()


def main():
    parser = argparse.ArgumentParser(description="Get events for a Kubernetes pod")
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
                "get_pod_events",
                {"pod_name": args.pod_name, "namespace": args.namespace},
            )
            event_list = result.get("events", [])
        else:
            core_v1 = get_k8s_client()
            events = core_v1.list_namespaced_event(
                namespace=args.namespace,
                field_selector=f"involvedObject.name={args.pod_name}",
            )

            event_list = []
            for event in events.items:
                event_list.append(
                    {
                        "type": event.type,
                        "reason": event.reason,
                        "message": event.message,
                        "count": event.count,
                        "first_timestamp": str(event.first_timestamp),
                        "last_timestamp": str(event.last_timestamp),
                    }
                )

            # Sort by last timestamp (most recent first)
            event_list.sort(key=lambda x: x["last_timestamp"] or "", reverse=True)

        if args.json:
            print(
                json.dumps(
                    {
                        "pod": args.pod_name,
                        "namespace": args.namespace,
                        "event_count": len(event_list),
                        "events": event_list,
                    },
                    indent=2,
                )
            )
        else:
            format_events(args.pod_name, args.namespace, event_list)

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
