#!/bin/bash
# One-time setup: Add GitHub App secrets to AWS Secrets Manager
# Usage: ./setup-github-secrets.sh
set -e

REGION="us-west-2"
SECRET_NAME="opensre/prod/github-app"

echo "🔐 Setting up GitHub App secrets in AWS Secrets Manager"
echo "======================================================="
echo ""

# Check if env vars are set
if [ -z "$GITHUB_APP_ID" ]; then
  echo "❌ Error: GITHUB_APP_ID is not set"
  echo ""
  echo "Please set the following environment variables before running:"
  echo "  export GITHUB_APP_ID='your-app-id'"
  echo "  export GITHUB_APP_CLIENT_ID='your-client-id'"
  echo "  export GITHUB_APP_CLIENT_SECRET='your-client-secret'"
  echo "  export GITHUB_APP_WEBHOOK_SECRET='your-webhook-secret'"
  echo "  export GITHUB_APP_PRIVATE_KEY_B64='base64-encoded-private-key'"
  echo ""
  echo "Or for the private key from a file:"
  echo "  export GITHUB_APP_PRIVATE_KEY_B64=\$(base64 -i /path/to/private-key.pem)"
  echo ""
  exit 1
fi

# Decode the private key
GITHUB_APP_PRIVATE_KEY=$(echo "$GITHUB_APP_PRIVATE_KEY_B64" | base64 -d)

echo "1️⃣  Creating/updating secret in AWS Secrets Manager..."

# Create the JSON payload (using jq to properly escape the private key)
SECRET_JSON=$(jq -n \
  --arg app_id "$GITHUB_APP_ID" \
  --arg client_id "$GITHUB_APP_CLIENT_ID" \
  --arg client_secret "$GITHUB_APP_CLIENT_SECRET" \
  --arg webhook_secret "$GITHUB_APP_WEBHOOK_SECRET" \
  --arg private_key "$GITHUB_APP_PRIVATE_KEY" \
  '{
    app_id: $app_id,
    client_id: $client_id,
    client_secret: $client_secret,
    webhook_secret: $webhook_secret,
    private_key: $private_key
  }')

# Check if secret exists
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region $REGION > /dev/null 2>&1; then
  echo "   Secret exists, updating..."
  aws secretsmanager update-secret \
    --secret-id "$SECRET_NAME" \
    --secret-string "$SECRET_JSON" \
    --region $REGION > /dev/null
else
  echo "   Creating new secret..."
  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "GitHub App credentials for OpenSRE" \
    --secret-string "$SECRET_JSON" \
    --region $REGION > /dev/null
fi

echo "   ✅ Secret stored in AWS Secrets Manager"
echo ""
echo "2️⃣  Verifying secret..."
aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --region $REGION --query 'SecretString' --output text | jq '{app_id, client_id, webhook_secret: "***", client_secret: "***", private_key: "***"}'
echo ""
echo "✅ GitHub App secrets configured!"
echo ""
echo "Next steps:"
echo "1. Run the deploy workflow to pick up the new secrets:"
echo "   gh workflow run deploy-config-service-prod.yml"
echo ""
echo "2. Configure your GitHub App with these URLs:"
echo "   Callback URL: https://ui.opensre.ai/github/callback"
echo "   Setup URL:    https://ui.opensre.ai/integrations/github/setup"
echo "   Webhook URL:  https://ui.opensre.ai/webhooks/github"
echo ""
