#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# Generate a Docker-network-compatible kubeconfig from a running
# kind cluster.  The standard kubeconfig points at 127.0.0.1:<port>
# which is unreachable from inside a Docker Compose service.
# This script rewrites the server URL to point at the kind
# control-plane container by name and enables insecure-skip-tls-verify.
# ─────────────────────────────────────────────────────────────────

CLUSTER_NAME="${1:-opensre-test}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$SCRIPT_DIR/kubeconfig-docker.yaml"

echo "[generate-kubeconfig] Exporting kubeconfig for kind cluster '$CLUSTER_NAME'..."

# Get the raw kubeconfig from kind
kind get kubeconfig --name "$CLUSTER_NAME" > "$OUTPUT"

# Patch for Docker network:
#   - Replace server URL 127.0.0.1:<port> → <cluster>-control-plane:6443
#   - Remove certificate-authority-data (won't match container hostname)
#   - Add insecure-skip-tls-verify: true
python3 -c "
import re, sys

with open('$OUTPUT') as f:
    text = f.read()

# Rewrite server URL
text = re.sub(
    r'server: https://127\.0\.0\.1:\d+',
    'server: https://${CLUSTER_NAME}-control-plane:6443',
    text,
)

# Remove certificate-authority-data and add insecure-skip-tls-verify
text = re.sub(
    r'certificate-authority-data: \S+',
    'insecure-skip-tls-verify: true',
    text,
)

with open('$OUTPUT', 'w') as f:
    f.write(text)
"

echo "[generate-kubeconfig] Written to $OUTPUT"
