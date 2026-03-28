## Terraform: OpenSRE Config Service (App) — Internal UI Endpoint

This stack deploys the **opensre-config-service API + UI** as an **internal-only** endpoint:
- **ECS Fargate** service (private subnets)
- **Internal ALB** (private subnets) routing to the service
- **ECR** repository to store the container image

### Why this is the recommended dev path (no VPN required)
The ALB is **internal** (not internet-facing). To access it from your laptop for dev/test, you can use **SSM port-forwarding** via the existing jumpbox.

### Prerequisites
- AWS profile: `playground`
- Region: `us-west-2`
- Docker installed locally
- The RDS stack already applied (so the Secrets Manager secret exists)

### Quick start (deploy)
1) Build + push image to ECR (helper script in repo root):

```bash
./scripts/deploy_app_ecs.sh
```

2) (Alternative) Terraform only:

```bash
cd infra/terraform/app
terraform init
terraform apply -var 'aws_profile=playground'
```

### Access the UI (internal)
Start an SSM tunnel to the internal ALB via jumpbox:

```bash
./scripts/ui_tunnel_aws.sh
```

Then open:
- `http://localhost:8081/` (default)


