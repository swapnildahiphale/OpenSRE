## Terraform: OpenSRE Config Service (RDS PostgreSQL)

This Terraform module provisions an **AWS RDS PostgreSQL** instance inside an **existing VPC**, intended to be used by `opensre-config-service` running inside the same VPC (e.g., alongside your OTel demo microservices).

### What it creates
- **RDS PostgreSQL** instance (private, not publicly accessible)
- **DB subnet group** (using existing private subnets)
- **Security group** for the DB
- **Secrets Manager** secret storing the DB credentials (recommended)
- Optional: DB parameter group (defaults enforce SSL)

### Prerequisites
- AWS credentials configured locally
- Profile: `playground`
- Region: `us-west-2` (default; configurable)

### Quick start

> Note: this directory is the original RDS Terraform. If you lost local Terraform state,
> do **not** re-apply blindly (it may try to recreate resources). For local DB access,
> use the dedicated `infra/terraform/jumpbox` stack and SSM port-forwarding.

1) Copy example vars:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2) Edit `terraform.tfvars` (VPC + private subnets already filled for `opensre-demo-vpc`).

3) Run:

```bash
cd infra/terraform
terraform init
terraform plan  -var 'aws_profile=playground'
terraform apply -var 'aws_profile=playground'
```

### Outputs
- `db_endpoint`
- `db_port`
- `db_name`
- `db_security_group_id`
- `db_secret_arn`

### Notes (enterprise hygiene)
- The instance is created in **private subnets** only.
- Password is generated and stored in **AWS Secrets Manager**.
- `deletion_protection` is configurable (default false for playground).


