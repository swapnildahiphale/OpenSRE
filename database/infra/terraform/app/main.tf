provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

locals {
  tags = merge({ Project = var.project }, var.tags)
  name = var.project
  # Some AWS resources have strict name length limits (e.g. ALB: 32 chars).
  # Keep full `project` for tagging and most resources, but derive safe shortened names where needed.
  # NOTE: Terraform v1.5.x does not include regexreplace(); keep this simple.
  # We expect `project` to already be in a safe slug format (lowercase + hyphens).
  name_safe = lower(replace(var.project, "_", "-"))
  alb_name  = "${substr(local.name_safe, 0, 23)}-internal" # 23 + len("-internal") == 32
  tg_name   = "${substr(local.name_safe, 0, 29)}-tg"       # 29 + len("-tg") == 32
}

data "aws_vpc" "target" {
  id = var.vpc_id
}

data "aws_secretsmanager_secret" "db" {
  name = var.db_secret_name
}

data "aws_secretsmanager_secret" "token_pepper" {
  name = var.token_pepper_secret_name
}

data "aws_secretsmanager_secret" "admin_token" {
  name = var.admin_token_secret_name
}

# ---------- ECR ----------

resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = local.tags
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "keep last 30 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = { type = "expire" }
      }
    ]
  })
}

# ---------- CloudWatch logs ----------

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = 14
  tags              = local.tags
}

# ---------- Networking ----------

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Internal ALB SG for ${local.name}"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from VPC"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "service" {
  name        = "${local.name}-svc"
  description = "ECS service SG for ${local.name}"
  vpc_id      = var.vpc_id

  ingress {
    description     = "App traffic from ALB"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_lb" "alb" {
  name               = local.alb_name
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.private_subnet_ids
  tags               = local.tags
}

resource "aws_lb_target_group" "app" {
  name        = local.tg_name
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
  }

  tags = local.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ---------- ECS ----------

resource "aws_ecs_cluster" "cluster" {
  name = "${local.name}-cluster"
  tags = local.tags
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name}-ecs-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name = "${local.name}-ecs-exec-secrets"
  role = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          data.aws_secretsmanager_secret.db.arn,
          "${data.aws_secretsmanager_secret.db.arn}:*",
          data.aws_secretsmanager_secret.token_pepper.arn,
          "${data.aws_secretsmanager_secret.token_pepper.arn}:*",
          data.aws_secretsmanager_secret.admin_token.arn,
          "${data.aws_secretsmanager_secret.admin_token.arn}:*"
        ]
      }
    ]
  })
}

resource "aws_ecs_task_definition" "app" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn        = aws_iam_role.task_execution.arn

  runtime_platform {
    cpu_architecture        = var.cpu_architecture
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "DB_SSLMODE", value = "require" }
      ]
      secrets = [
        { name = "DB_HOST", valueFrom = "${data.aws_secretsmanager_secret.db.arn}:host::" },
        { name = "DB_PORT", valueFrom = "${data.aws_secretsmanager_secret.db.arn}:port::" },
        { name = "DB_NAME", valueFrom = "${data.aws_secretsmanager_secret.db.arn}:dbname::" },
        { name = "DB_USERNAME", valueFrom = "${data.aws_secretsmanager_secret.db.arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${data.aws_secretsmanager_secret.db.arn}:password::" },
        { name = "TOKEN_PEPPER", valueFrom = data.aws_secretsmanager_secret.token_pepper.arn },
        { name = "ADMIN_TOKEN", valueFrom = data.aws_secretsmanager_secret.admin_token.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.app.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = local.name
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]
  tags       = local.tags
}


