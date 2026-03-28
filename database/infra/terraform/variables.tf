variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-west-2"
}

variable "aws_profile" {
  type        = string
  description = "AWS CLI profile name"
  default     = "playground"
}

variable "project" {
  type        = string
  description = "Tag prefix / project name"
  default     = "opensre-config-service"
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID to deploy into"
  default     = "vpc-0949ea4cf60f4aa72"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for RDS subnet group"
  default     = ["subnet-0b361bbf3330457b8", "subnet-0ea37c7ded57bf10c"]
}

variable "db_name" {
  type        = string
  description = "Initial database name"
  default     = "opensre_config"
}

variable "db_username" {
  type        = string
  description = "Master username"
  default     = "opensre"
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.micro"
}

variable "db_identifier" {
  type        = string
  description = "RDS DB instance identifier (DBInstanceIdentifier)"
  default     = "opensre-config-service-postgres"
}

variable "db_security_group_name" {
  type        = string
  description = "Name for the DB security group (ForceNew; must match existing if importing)."
  default     = "brownie-config-service-db"
}

variable "db_subnet_group_name" {
  type        = string
  description = "Name for the DB subnet group (ForceNew; must match existing if importing)."
  default     = "brownie-config-service-db-subnets"
}

variable "db_parameter_group_name" {
  type        = string
  description = "Name for the DB parameter group (ForceNew; must match existing if importing)."
  default     = "brownie-config-service-pg"
}

variable "db_secret_name" {
  type        = string
  description = "Secrets Manager secret name that stores RDS connection info (ForceNew; must match existing if importing)."
  default     = "opensre-config-service/rds"
}

variable "db_engine_version" {
  type        = string
  description = "PostgreSQL engine version"
  default     = "16.11"
}

variable "db_allocated_storage_gb" {
  type        = number
  description = "Allocated storage in GB"
  default     = 20
}

variable "db_max_allocated_storage_gb" {
  type        = number
  description = "Max autoscaled storage in GB"
  default     = 100
}

variable "db_backup_retention_days" {
  type        = number
  description = "Backup retention"
  default     = 7
}

variable "db_deletion_protection" {
  type        = bool
  description = "Enable deletion protection"
  default     = true
}

variable "db_multi_az" {
  type        = bool
  description = "Enable Multi-AZ"
  default     = false
}

variable "allowed_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the DB (should be VPC CIDR or app subnets)."
  default     = ["10.0.0.0/16"]
}

variable "tags" {
  type        = map(string)
  description = "Extra tags"
  default     = {}
}

variable "jumpbox_enabled" {
  type        = bool
  description = "Create a private SSM-managed jumpbox for DB access from local machine"
  default     = true
}

variable "jumpbox_subnet_id" {
  type        = string
  description = "Subnet ID for the jumpbox (should be private)"
  default     = "subnet-0b361bbf3330457b8"
}

variable "manage_db_secret_version" {
  type        = bool
  description = "Whether Terraform should manage (create/update) the DB connection secret version string. Set false when importing existing infra to avoid rotating secrets."
  default     = true
}


