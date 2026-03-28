variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-west-2"
}

variable "name_prefix" {
  type        = string
  description = "Name prefix for resources"
  default     = "opensre-web-ui"
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID to deploy into"
  default     = "vpc-0949ea4cf60f4aa72"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for ALB (internet-facing) or internal ALB endpoints"
  default     = ["subnet-06a388f902a281163", "subnet-066b9fb122c35d783"]
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for ECS tasks"
  default     = ["subnet-0b361bbf3330457b8", "subnet-0ea37c7ded57bf10c"]
}

variable "ecs_cluster_name" {
  type        = string
  description = "ECS cluster name to deploy the service into"
  default     = "opensre-config-service-cluster"
}

variable "image_uri" {
  type        = string
  description = "Full container image URI (ECR repo URI + tag)"
}

variable "desired_count" {
  type        = number
  description = "Number of tasks"
  default     = 1
}

variable "cpu" {
  type        = number
  description = "Fargate CPU units"
  default     = 512
}

variable "memory" {
  type        = number
  description = "Fargate memory (MiB)"
  default     = 1024
}

variable "container_port" {
  type        = number
  description = "Container port"
  default     = 3000
}

variable "alb_internal" {
  type        = bool
  description = "Whether the ALB is internal (true) or internet-facing (false)"
  default     = true
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS (optional). If empty, only HTTP listener will be created."
  default     = ""
}

variable "config_service_url" {
  type        = string
  description = "Base URL of the backend config service (reachable from ECS tasks inside the VPC)"
  # Note: this is an internal ALB DNS name; ALBs typically listen on 80/443 (not the target port 8080).
  default = "http://internal-opensre-config-service.internal"
}

variable "enable_ssm_tunnel" {
  type        = bool
  description = "Create a tiny SSM-managed instance you can use to port-forward to the internal ALB from your laptop (no inbound ports opened)."
  default     = true
}

variable "ssm_tunnel_subnet_id" {
  type        = string
  description = "Subnet for the SSM tunnel instance (recommend: a public subnet so it can reach SSM via IGW without requiring VPC endpoints/NAT)."
  default     = "subnet-06a388f902a281163"
}

variable "ssm_tunnel_instance_type" {
  type        = string
  description = "Instance type for the SSM tunnel instance"
  default     = "t4g.nano"
}


