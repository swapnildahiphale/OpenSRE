## OpenSRE Web UI (ECS/Fargate)

This Terraform stack deploys the Next.js web UI to ECS/Fargate in an existing VPC and exposes it via an ALB.

### What it creates
- **ECR repo** (optional usage): `opensre-web-ui`
- **CloudWatch log group**
- **IAM roles** for ECS task execution
- **ALB + target group + listener** (internal by default)
- **ECS task definition + ECS service** (Fargate, in private subnets)
- **Optional**: an **SSM tunnel instance** (no inbound) to reach the internal ALB from your laptop via port-forwarding

### Prereqs
- AWS credentials (this repo was inspected with `--profile playground` in account `103002841599`)
- Docker installed (to build/push image to ECR)
- Terraform installed

### Deploy (example)

1) Build & push the image to ECR:

```bash
export AWS_PROFILE=playground
export AWS_REGION=us-west-2

REPO_URI="$(aws ecr describe-repositories --repository-names opensre-web-ui --query 'repositories[0].repositoryUri' --output text 2>/dev/null || true)"
if [ -z "$REPO_URI" ] || [ "$REPO_URI" = "None" ]; then
  REPO_URI="$(aws ecr create-repository --repository-name opensre-web-ui --query 'repository.repositoryUri' --output text)"
fi

aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO_URI%/*}"

IMAGE_TAG="$(date +%Y%m%d%H%M%S)"
docker build -t opensre-web-ui:${IMAGE_TAG} ../..
docker tag opensre-web-ui:${IMAGE_TAG} ${REPO_URI}:${IMAGE_TAG}
docker push ${REPO_URI}:${IMAGE_TAG}
```

2) Apply Terraform:

```bash
cd infra/terraform
terraform init
terraform apply -auto-approve \
  -var "image_uri=${REPO_URI}:${IMAGE_TAG}"
```

3) Open the output ALB DNS name.

### Access when ALB is internal (recommended)
This stack defaults to an **internal ALB** (`alb_internal=true`). That means you can’t hit it directly from the public internet.

If you want local access from your laptop without making it internet-facing, Terraform can create a tiny **SSM-managed tunnel instance** (no inbound ports) and you can port-forward to the internal ALB:

#### Option A: helper script (recommended)

```bash
chmod +x infra/terraform/scripts/ssm_tunnel.sh
AWS_PROFILE=playground AWS_REGION=us-west-2 infra/terraform/scripts/ssm_tunnel.sh
```

Then open `http://localhost:8081`.

#### Option B: raw AWS CLI command

```bash
export AWS_PROFILE=playground
export AWS_REGION=us-west-2

# Run the output command (prints after terraform apply)
aws ssm start-session \
  --target <ssm_tunnel_instance_id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["<internal-alb-dns>"],"portNumber":["80"],"localPortNumber":["8081"]}'
```

Then open `http://localhost:8081`.

Notes:
- This requires the AWS **Session Manager plugin** (normally bundled with AWS CLI v2 on macOS).
- The tunnel instance is placed in a **public subnet** by default so it can reach SSM without needing VPC endpoints.

### Runtime configuration
The ECS task sets these environment variables (you can change them in `ecs.tf`):
- `CONFIG_SERVICE_URL`: base URL for your backend config service (expected reachable from the task in VPC)

