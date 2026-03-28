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
  description = "Project name prefix"
  default     = "opensre-config-service"
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID"
  default     = "vpc-0949ea4cf60f4aa72"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for ALB + ECS tasks"
  default     = ["subnet-0b361bbf3330457b8", "subnet-0ea37c7ded57bf10c"]
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR allowed to access the internal ALB"
  default     = "10.0.0.0/16"
}

variable "jumpbox_instance_id" {
  type        = string
  description = "Existing SSM jumpbox instance ID (used for SSM tunneling to internal ALB)"
  default     = ""
}

variable "container_port" {
  type        = number
  description = "Container port exposed by the app"
  default     = 8080
}

variable "desired_count" {
  type        = number
  description = "ECS desired task count"
  default     = 1
}

variable "cpu" {
  type        = number
  description = "Fargate CPU units"
  default     = 256
}

variable "cpu_architecture" {
  type        = string
  description = "Fargate CPU architecture (ARM64 or X86_64)."
  default     = "ARM64"
}

variable "memory" {
  type        = number
  description = "Fargate memory (MiB)"
  default     = 512
}

variable "image_tag" {
  type        = string
  description = "Container image tag"
  default     = "latest"
}

variable "token_pepper_secret_name" {
  type        = string
  description = "Secrets Manager secret name containing TOKEN_PEPPER as a plaintext secret string"
  default     = "opensre-config-service/token_pepper"
}

variable "admin_token_secret_name" {
  type        = string
  description = "Secrets Manager secret name containing ADMIN_TOKEN as a plaintext secret string"
  default     = "opensre-config-service/admin_token"
}

variable "db_secret_name" {
  type        = string
  description = "Secrets Manager secret name that contains RDS connection JSON {username,password,host,port,dbname}"
  default     = "opensre-config-service/rds"
}

variable "tags" {
  type        = map(string)
  description = "Extra tags"
  default     = {}
}


