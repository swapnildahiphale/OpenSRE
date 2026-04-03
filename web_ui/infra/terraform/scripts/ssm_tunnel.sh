#!/usr/bin/env bash
set -euo pipefail

# Start an SSM port-forward session from your laptop to the *internal* ALB.
#
# Usage:
#   ./infra/terraform/scripts/ssm_tunnel.sh
#
# Optional env vars:
#   AWS_PROFILE=playground
#   AWS_REGION=us-west-2
#   LOCAL_PORT=8081
#   REMOTE_PORT=80
#
# Notes:
# - Requires: terraform, awscli v2, session-manager-plugin
# - Run from repo root (script will cd into infra/terraform)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# scripts/ is inside infra/terraform/, so TF_DIR is one level up.
TF_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

AWS_PROFILE="${AWS_PROFILE:-}"
AWS_REGION="${AWS_REGION:-us-west-2}"
LOCAL_PORT="${LOCAL_PORT:-8081}"
REMOTE_PORT="${REMOTE_PORT:-80}"

cd "${TF_DIR}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "ERROR: terraform not found in PATH" >&2
  exit 1
fi
if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws not found in PATH" >&2
  exit 1
fi

TUNNEL_INSTANCE_ID="$(terraform output -raw ssm_tunnel_instance_id 2>/dev/null || true)"
ALB_DNS_NAME="$(terraform output -raw alb_dns_name 2>/dev/null || true)"

if [[ -z "${TUNNEL_INSTANCE_ID}" || "${TUNNEL_INSTANCE_ID}" == "null" ]]; then
  echo "ERROR: terraform output ssm_tunnel_instance_id is empty/null. Is enable_ssm_tunnel=true and applied?" >&2
  exit 1
fi

if [[ -z "${ALB_DNS_NAME}" || "${ALB_DNS_NAME}" == "null" ]]; then
  echo "ERROR: terraform output alb_dns_name is empty/null. Did terraform apply succeed?" >&2
  exit 1
fi

echo "Starting SSM port-forward..."
echo "- instance: ${TUNNEL_INSTANCE_ID}"
echo "- remote:   ${ALB_DNS_NAME}:${REMOTE_PORT}"
echo "- local:    localhost:${LOCAL_PORT}"

AWS_ARGS=()
if [[ -n "${AWS_PROFILE}" ]]; then
  AWS_ARGS+=(--profile "${AWS_PROFILE}")
fi
AWS_ARGS+=(--region "${AWS_REGION}")

exec aws "${AWS_ARGS[@]}" ssm start-session \
  --target "${TUNNEL_INSTANCE_ID}" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"${ALB_DNS_NAME}\"],\"portNumber\":[\"${REMOTE_PORT}\"],\"localPortNumber\":[\"${LOCAL_PORT}\"]}"


