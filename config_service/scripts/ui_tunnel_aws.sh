#!/usr/bin/env bash
set -euo pipefail

# Open an SSM port-forward tunnel to the *internal* ALB so you can access the UI locally.
#
# This avoids VPN for dev/testing:
# - ALB stays internal-only (not internet-facing)
# - Your laptop uses SSM to a private jumpbox, then forwards to the ALB DNS inside the VPC
#
# Usage:
#   AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/ui_tunnel_aws.sh
#
# Then open:
#   http://localhost:8081/

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MONO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
TF_DIR="$MONO_ROOT/database/infra/terraform/app"
JUMPBOX_TF_DIR="$MONO_ROOT/database/infra/terraform/jumpbox"

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"
LOCAL_PORT="${LOCAL_PORT:-8081}"
REMOTE_PORT="${REMOTE_PORT:-80}"
JUMPBOX_INSTANCE_ID="${JUMPBOX_INSTANCE_ID:-}"

sanitize_dns () {
  # Accept only a plain DNS hostname (no spaces / no terraform warning text).
  local candidate="${1:-}"
  printf '%s\n' "${candidate}" | tr -d '\r' | tr -d ' \t' | grep -E '^[A-Za-z0-9.-]+$' || true
}

ALB_DNS=""
if [ -d "$TF_DIR" ]; then
  ALB_DNS="$(terraform -chdir="$TF_DIR" output -raw alb_dns_name 2>/dev/null || true)"
fi
ALB_DNS="$(sanitize_dns "${ALB_DNS}")"

if [ -z "$ALB_DNS" ]; then
  # Fallback: discover internal ALB by tag (works even if terraform state/outputs are missing locally).
  ALB_DNS="$(
    AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" python3 - <<'PY'
import json, os, subprocess, sys

profile = os.environ["AWS_PROFILE"]
region = os.environ["AWS_REGION"]
project = "opensre-config-service"

lbs = json.loads(subprocess.check_output(
    ["aws","--profile",profile,"--region",region,"elbv2","describe-load-balancers","--output","json"],
    text=True,
))

internal = [lb for lb in lbs.get("LoadBalancers", []) if lb.get("Scheme") == "internal"]
for lb in internal:
    arn = lb.get("LoadBalancerArn")
    if not arn:
        continue
    tags = json.loads(subprocess.check_output(
        ["aws","--profile",profile,"--region",region,"elbv2","describe-tags","--resource-arns",arn,"--output","json"],
        text=True,
    ))
    tag_list = (tags.get("TagDescriptions", [{}])[0].get("Tags") or [])
    tag_map = {t.get("Key"): t.get("Value") for t in tag_list}
    if tag_map.get("Project") == project:
        dns = lb.get("DNSName") or ""
        if dns:
            print(dns)
            sys.exit(0)
sys.exit(0)
PY
  )"
  ALB_DNS="$(sanitize_dns "${ALB_DNS}")"
fi

if [ -z "$ALB_DNS" ]; then
  echo "Could not determine ALB DNS name." >&2
  echo "Either deploy (so terraform outputs exist) or set ALB_DNS explicitly." >&2
  echo "Example: ALB_DNS=internal-xxxxx.us-west-2.elb.amazonaws.com make ui-tunnel" >&2
  exit 1
fi

JUMPBOX_ID="$JUMPBOX_INSTANCE_ID"
if [ -z "$JUMPBOX_ID" ]; then
  # Prefer Terraform output if available (works even if the jumpbox tag name differs during renames).
  if [ -d "$JUMPBOX_TF_DIR" ]; then
    JUMPBOX_ID="$(terraform -chdir="$JUMPBOX_TF_DIR" output -raw jumpbox_instance_id 2>/dev/null || true)"
  fi
fi

sanitize_instance_id () {
  # Accept only actual EC2 instance IDs (e.g. i-0123abcd...). Terraform warnings can leak into stdout.
  local candidate="${1:-}"
  printf '%s\n' "${candidate}" | tr -d '\r' | grep -E '^i-[0-9a-f]{8,}$' || true
}

JUMPBOX_ID="$(sanitize_instance_id "${JUMPBOX_ID}")"

if [ -z "$JUMPBOX_ID" ]; then
  # Prefer Terraform project tag (most robust).
  JUMPBOX_ID="$(
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ec2 describe-instances \
      --filters "Name=tag:Project,Values=opensre-config-service" "Name=instance-state-name,Values=running" \
      --query "Reservations[0].Instances[0].InstanceId" --output text 2>/dev/null || true
  )"
fi

JUMPBOX_ID="$(sanitize_instance_id "${JUMPBOX_ID}")"

if [ -z "$JUMPBOX_ID" ]; then
  # Find jumpbox by tag name (created by the RDS stack): Name=opensre-config-service-jumpbox
  JUMPBOX_ID="$(
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ec2 describe-instances \
      --filters "Name=tag:Name,Values=opensre-config-service-jumpbox" "Name=instance-state-name,Values=running" \
      --query "Reservations[0].Instances[0].InstanceId" --output text 2>/dev/null || true
  )"
fi

JUMPBOX_ID="$(sanitize_instance_id "${JUMPBOX_ID}")"

if [ -z "$JUMPBOX_ID" ] || [ "$JUMPBOX_ID" = "None" ]; then
  echo "Could not find a running jumpbox instance."
  echo "Expected tag: Name=opensre-config-service-jumpbox"
  echo "Or set JUMPBOX_INSTANCE_ID explicitly."
  echo "If you used the standalone jumpbox stack, update this script or tag your instance."
  exit 1
fi

echo "Tunneling via jumpbox: $JUMPBOX_ID"
echo "Forwarding localhost:$LOCAL_PORT -> ${ALB_DNS}:$REMOTE_PORT"
echo "Open: http://localhost:$LOCAL_PORT/"
echo ""

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ssm start-session \
  --target "$JUMPBOX_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "host=${ALB_DNS},portNumber=${REMOTE_PORT},localPortNumber=${LOCAL_PORT}"


