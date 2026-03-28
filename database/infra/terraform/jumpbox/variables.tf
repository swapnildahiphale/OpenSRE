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

variable "subnet_id" {
  type        = string
  description = "Private subnet ID for jumpbox"
  default     = "subnet-0b361bbf3330457b8"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type"
  default     = "t4g.nano"
}

variable "tags" {
  type        = map(string)
  description = "Extra tags"
  default     = {}
}


