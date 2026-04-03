#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper to apply Terraform for RDS.
# NOTE: Terraform state is local by default; for team usage, set up a remote backend.

AWS_PROFILE="${AWS_PROFILE:-playground}"
AWS_REGION="${AWS_REGION:-us-west-2}"

cd infra/terraform
terraform init -input=false
terraform apply -auto-approve -input=false -var "aws_profile=${AWS_PROFILE}" -var "aws_region=${AWS_REGION}"


