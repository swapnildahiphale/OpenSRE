#!/usr/bin/env python3
"""List available K8s clusters.

In gateway mode (K8S_GATEWAY_URL set): lists remote clusters from config-service.
In direct mode (kubeconfig available): lists contexts from kubeconfig.

Usage:
    python list_clusters.py
    python list_clusters.py --json
"""

import argparse
import json
import os
import sys


def list_kubeconfig_contexts():
    """List clusters from local kubeconfig."""
    try:
        from kubernetes import config as k8s_config

        contexts, active_context = k8s_config.list_kube_config_contexts()
        if not contexts:
            return []
        active_name = active_context.get("name", "") if active_context else ""
        result = []
        for ctx in contexts:
            name = ctx.get("name", "")
            cluster = ctx.get("context", {}).get("cluster", "")
            namespace = ctx.get("context", {}).get("namespace", "default")
            result.append(
                {
                    "name": name,
                    "cluster": cluster,
                    "namespace": namespace,
                    "active": name == active_name,
                    "mode": "direct (kubeconfig)",
                }
            )
        return result
    except Exception as e:
        print(f"Warning: Could not read kubeconfig: {e}", file=sys.stderr)
        return []


def list_gateway_clusters():
    """List remote clusters from config-service gateway."""
    import httpx

    config_url = os.environ.get("CONFIG_SERVICE_URL")
    if not config_url:
        return []

    headers = {}
    team_token = os.environ.get("TEAM_TOKEN")
    if team_token:
        headers["Authorization"] = f"Bearer {team_token}"
    else:
        tenant_id = os.environ.get("OPENSRE_TENANT_ID")
        team_id = os.environ.get("OPENSRE_TEAM_ID")
        if tenant_id and team_id:
            headers["X-Org-Id"] = tenant_id
            headers["X-Team-Node-Id"] = team_id

    try:
        url = f"{config_url.rstrip('/')}/api/v1/team/k8s-clusters"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
        if response.status_code == 404 or response.status_code >= 400:
            return []
        clusters = response.json()
        for c in clusters:
            c["mode"] = "gateway (remote)"
        return clusters or []
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="List available K8s clusters")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Try both sources
    gateway_clusters = list_gateway_clusters()
    kubeconfig_contexts = list_kubeconfig_contexts()

    if args.json:
        print(
            json.dumps(
                {
                    "gateway_clusters": gateway_clusters,
                    "kubeconfig_contexts": kubeconfig_contexts,
                },
                indent=2,
            )
        )
        return

    if gateway_clusters:
        print(f"Gateway clusters: {len(gateway_clusters)}")
        print(f"{'CLUSTER ID':<38} {'NAME':<25} {'STATUS':<14}")
        print("-" * 77)
        for c in gateway_clusters:
            print(
                f"{c.get('cluster_id', ''):<38} {c.get('cluster_name', ''):<25} {c.get('status', '?'):<14}"
            )
        print()

    if kubeconfig_contexts:
        print(f"Local kubeconfig contexts: {len(kubeconfig_contexts)}")
        print(f"{'CONTEXT':<40} {'CLUSTER':<30} {'ACTIVE'}")
        print("-" * 77)
        for ctx in kubeconfig_contexts:
            active = "*" if ctx["active"] else ""
            print(f"{ctx['name']:<40} {ctx['cluster']:<30} {active}")
        print()
        if not gateway_clusters and not os.environ.get("K8S_GATEWAY_URL"):
            print(
                "K8S_GATEWAY_URL is not set: gateway mode is unavailable, so "
                "--cluster-id will be silently ignored by every script (they all "
                "fall back to the context marked * above). Do NOT pass --cluster-id "
                "or try multiple contexts — run scripts with just -n <namespace>; "
                "you will always hit the active context above."
            )
        else:
            print("Use these contexts with: kubectl --context <CONTEXT_NAME>")
            print("Or run scripts without --cluster-id to use the active context.")

    if not gateway_clusters and not kubeconfig_contexts:
        print("No K8s clusters found.")
        print("  - For local: ensure ~/.kube/config exists")
        print("  - For remote: configure K8S_GATEWAY_URL and register clusters")


if __name__ == "__main__":
    main()
