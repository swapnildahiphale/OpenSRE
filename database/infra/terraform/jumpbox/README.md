## Terraform: SSM Jumpbox (Private)

This stack creates a tiny EC2 instance in a **private subnet** with **SSM enabled**.
It enables:
- Local `psql` access to private RDS via SSM port-forward
- Running migrations from your laptop without making RDS public

### Why this exists
RDS is in private subnets and is not reachable from your laptop. SSM provides secure access without opening inbound ports.

### Usage

```bash
cd infra/terraform/jumpbox
terraform init
terraform apply -auto-approve -var 'aws_profile=playground' -var 'aws_region=us-west-2'
```

Outputs:
- `jumpbox_instance_id`


