data "aws_vpc" "this" {
  id = var.vpc_id
}

data "aws_ecs_cluster" "this" {
  cluster_name = var.ecs_cluster_name
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.name_prefix}"
  retention_in_days = 14
}

resource "aws_ecr_repository" "app" {
  name                 = var.name_prefix
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}


