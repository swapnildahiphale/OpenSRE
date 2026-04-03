#!/usr/bin/env bash
set -euo pipefail

# Creates (if missing) a plaintext Secrets Manager secret used for TOKEN_PEPPER.
#
# Usage:
#   AWS_PROFILE=playground AWS_REGION=us-west-2 ./scripts/create_token_pepper_secret.sh
#
# Outputs:
#   Secret ARN

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"
SECRET_NAME="${SECRET_NAME:-opensre-config-service/token_pepper}"

if aws --profile "$AWS_PROFILE" --region "$AWS_REGION" secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
  aws --profile "$AWS_PROFILE" --region "$AWS_REGION" secretsmanager describe-secret --secret-id "$SECRET_NAME" --query ARN --output text
  exit 0
fi

PEPPER="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" secretsmanager create-secret \
  --name "$SECRET_NAME" \
  --description "opensre-config-service TOKEN_PEPPER (server-side pepper for hashing opaque bearer tokens)" \
  --secret-string "$PEPPER" \
  --query ARN --output text


