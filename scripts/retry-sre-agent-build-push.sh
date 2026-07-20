#!/usr/bin/env bash
# Retry sre-agent amd64 build + ECR push until network succeeds.
# Usage: ECR_IMAGE=... AWS_PROFILE=... ./scripts/retry-sre-agent-build-push.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ECR_REGISTRY="${ECR_REGISTRY:-123456789012.dkr.ecr.us-west-1.amazonaws.com}"
IMAGE="${ECR_IMAGE:-${ECR_REGISTRY}/opensre/sre-agent:pilot}"
AWS_PROFILE="${AWS_PROFILE:-your-aws-profile}"
AWS_REGION="${AWS_REGION:-us-west-1}"
LOG="${ROOT}/.retry-sre-agent-build.log"
INTERVAL="${RETRY_INTERVAL_SEC:-3600}"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

attempt=0
while true; do
  attempt=$((attempt + 1))
  log "Attempt ${attempt}: docker build ${IMAGE}"

  if docker build --platform linux/amd64 -t "$IMAGE" "${ROOT}/sre-agent" >>"$LOG" 2>&1; then
    log "Build OK — logging into ECR and pushing"
    if aws ecr get-login-password --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        | docker login --username AWS --password-stdin "$ECR_REGISTRY" >>"$LOG" 2>&1 \
      && docker push "$IMAGE" >>"$LOG" 2>&1; then
      log "SUCCESS: ${IMAGE} pushed"
      exit 0
    fi
    log "Push failed — will retry in ${INTERVAL}s"
  else
    log "Build failed (likely network) — retry in ${INTERVAL}s"
  fi

  sleep "$INTERVAL"
done
