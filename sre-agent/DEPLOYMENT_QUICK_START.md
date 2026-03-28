# Deployment Quick Start

## Local Development

### First Time
```bash
make setup-local
```
Creates Kind cluster with agent-sandbox controller, router, and secrets.

### Day-to-Day
```bash
make dev
```
Builds image, starts server on port 8000, auto-cleans on Ctrl+C.

Test with:
```bash
curl -X POST http://localhost:8000/investigate \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What is 2+2?"}'
```

### Other Local Commands
```bash
make dev-status     # Check what's running
make dev-logs       # View server/router logs
make dev-clean      # Manual sandbox cleanup
make dev-reset      # Delete Kind cluster (nuclear option)
```

---

## Production / Staging Deployment

Deployed via Helm charts through GitHub Actions:

```bash
# Staging (opensre-demo cluster)
gh workflow run deploy-eks.yml -f environment=staging -f services=all

# Production (opensre-prod cluster)
gh workflow run deploy-eks.yml -f environment=production -f services=all

# Deploy a single service
gh workflow run deploy-eks.yml -f environment=staging -f services=agent
```

### Manual Helm Deploy
```bash
aws eks update-kubeconfig --name opensre-demo --region us-west-2
cd charts
helm upgrade --install opensre ./opensre \
  -n opensre -f opensre/values.staging.yaml --timeout 5m
kubectl rollout restart deployment/opensre-agent -n opensre
```

### Check Production Status
```bash
kubectl get pods -n opensre-prod
kubectl logs -n opensre-prod deployment/opensre-agent --tail=50
```

---

## Docker Compose (Self-Hosted)

For running locally with docker-compose (no Kubernetes):
```bash
# From repo root
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
```

---

## Architecture

- **Helm charts**: `charts/opensre/` (staging: `values.staging.yaml`, prod: `values.prod.yaml`)
- **CI/CD**: `.github/workflows/deploy-eks.yml` builds all services and deploys via Helm
- **Agent image**: Built from `sre-agent/Dockerfile`, pushed to ECR as `opensre-agent`
- **Local dev**: Kind cluster with `make dev` (uses `sre-agent/scripts/`)
