#!/bin/bash
# Add GitHub App secrets to OpenSRE config-service
# Usage: ./add-github-app-secrets.sh
set -e

NAMESPACE="opensre"

echo "🔐 Adding GitHub App secrets to OpenSRE"
echo "============================================"
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
  echo "  export GITHUB_APP_PRIVATE_KEY=\$(cat /path/to/private-key.pem)"
  echo ""
  exit 1
fi

# Step 1: Get current secret values
echo "1️⃣  Reading current secret values..."
CURRENT_ADMIN_TOKEN=$(kubectl get secret opensre-config-service -n $NAMESPACE -o jsonpath='{.data.ADMIN_TOKEN}' | base64 -d)
CURRENT_TOKEN_PEPPER=$(kubectl get secret opensre-config-service -n $NAMESPACE -o jsonpath='{.data.TOKEN_PEPPER}' | base64 -d)
CURRENT_IMPERSONATION_JWT_SECRET=$(kubectl get secret opensre-config-service -n $NAMESPACE -o jsonpath='{.data.IMPERSONATION_JWT_SECRET}' | base64 -d)
echo "   ✅ Current values retrieved"

# Step 2: Update secret with GitHub App values
echo ""
echo "2️⃣  Updating secret with GitHub App values..."
kubectl create secret generic opensre-config-service \
  --namespace=$NAMESPACE \
  --from-literal=ADMIN_TOKEN="$CURRENT_ADMIN_TOKEN" \
  --from-literal=TOKEN_PEPPER="$CURRENT_TOKEN_PEPPER" \
  --from-literal=IMPERSONATION_JWT_SECRET="$CURRENT_IMPERSONATION_JWT_SECRET" \
  --from-literal=GITHUB_APP_ID="$GITHUB_APP_ID" \
  --from-literal=GITHUB_APP_CLIENT_ID="$GITHUB_APP_CLIENT_ID" \
  --from-literal=GITHUB_APP_CLIENT_SECRET="$GITHUB_APP_CLIENT_SECRET" \
  --from-literal=GITHUB_APP_WEBHOOK_SECRET="$GITHUB_APP_WEBHOOK_SECRET" \
  --from-literal=GITHUB_APP_NAME="${GITHUB_APP_NAME:-opensre}" \
  --from-literal=GITHUB_APP_PRIVATE_KEY="$GITHUB_APP_PRIVATE_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "   ✅ Secret updated"

# Step 3: Add env vars to config-service deployment
echo ""
echo "3️⃣  Adding environment variables to deployment..."
kubectl set env deployment/opensre-config-service -n $NAMESPACE \
  GITHUB_APP_ID- \
  GITHUB_APP_CLIENT_ID- \
  GITHUB_APP_CLIENT_SECRET- \
  GITHUB_APP_WEBHOOK_SECRET- \
  GITHUB_APP_NAME- \
  GITHUB_APP_PRIVATE_KEY- \
  GITHUB_SETUP_REDIRECT_URL- 2>/dev/null || true

kubectl set env deployment/opensre-config-service -n $NAMESPACE \
  --from=secret/opensre-config-service \
  --keys=GITHUB_APP_ID,GITHUB_APP_CLIENT_ID,GITHUB_APP_CLIENT_SECRET,GITHUB_APP_WEBHOOK_SECRET,GITHUB_APP_NAME,GITHUB_APP_PRIVATE_KEY

kubectl set env deployment/opensre-config-service -n $NAMESPACE \
  GITHUB_SETUP_REDIRECT_URL="https://ui.opensre.ai/integrations/github/setup"

echo "   ✅ Environment variables added"

# Step 4: Also update orchestrator's GITHUB_WEBHOOK_SECRET
echo ""
echo "4️⃣  Updating orchestrator's GITHUB_WEBHOOK_SECRET..."
kubectl set env deployment/opensre-orchestrator -n $NAMESPACE \
  GITHUB_WEBHOOK_SECRET="$GITHUB_APP_WEBHOOK_SECRET"
echo "   ✅ Orchestrator updated"

# Step 5: Wait for rollout
echo ""
echo "5️⃣  Waiting for rollouts..."
kubectl rollout status deployment/opensre-config-service -n $NAMESPACE --timeout=3m
kubectl rollout status deployment/opensre-orchestrator -n $NAMESPACE --timeout=3m

echo ""
echo "✅ GitHub App secrets configured!"
echo ""
echo "Next steps:"
echo "1. Configure your GitHub App with these URLs:"
echo "   Callback URL: https://ui.opensre.ai/github/callback"
echo "   Setup URL:    https://ui.opensre.ai/integrations/github/setup"
echo "   Webhook URL:  https://ui.opensre.ai/webhooks/github"
echo ""
echo "2. Run the database migration by redeploying config-service"
echo "   (the new migration file needs to be in the Docker image)"
echo ""
