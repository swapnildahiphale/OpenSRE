provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

locals {
  name_prefix = var.project
  tags = merge(
    {
      "Project" = var.project
    },
    var.tags
  )
}

data "aws_vpc" "target" {
  id = var.vpc_id
}

resource "aws_security_group" "db" {
  name        = var.db_security_group_name
  description = "RDS security group for ${var.project}"
  vpc_id      = var.vpc_id

  ingress {
    description = "Postgres from allowed CIDRs"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
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

resource "aws_db_subnet_group" "db" {
  name       = var.db_subnet_group_name
  subnet_ids = var.private_subnet_ids
  tags       = local.tags
}

resource "random_password" "db" {
  length  = 32
  special = true
  # RDS master password restrictions: disallow '/', '@', '"', and spaces.
  override_special = "!#$%&()*+-.:;<=>?[]^_{|}~"
}

resource "random_id" "final_snapshot" {
  byte_length = 4
}

resource "aws_secretsmanager_secret" "db" {
  name = var.db_secret_name
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  count     = var.manage_db_secret_version ? 1 : 0
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    host     = aws_db_instance.db.address
    port     = aws_db_instance.db.port
    dbname   = var.db_name
  })

  # When importing/managing an existing RDS instance, avoid accidentally rotating credentials
  # or creating a new secret version. Set manage_db_secret_version=false for that workflow.
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_db_parameter_group" "db" {
  name   = var.db_parameter_group_name
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = local.tags
}

resource "aws_db_instance" "db" {
  identifier = var.db_identifier

  engine         = "postgres"
  engine_version = var.db_engine_version

  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_max_allocated_storage_gb
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period = var.db_backup_retention_days
  deletion_protection     = var.db_deletion_protection
  skip_final_snapshot     = false
  final_snapshot_identifier = "${local.name_prefix}-final-${random_id.final_snapshot.hex}"

  parameter_group_name = aws_db_parameter_group.db.name

  tags = local.tags

  # Prevent Terraform from rotating the master password on imported/existing DBs.
  # Passwords should be rotated via a controlled procedure (and secret updates coordinated).
  lifecycle {
    ignore_changes = [password]
  }
}

# --- Private SSM jumpbox (for local port-forward to private RDS) ---

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }
}

resource "aws_security_group" "jumpbox" {
  count       = var.jumpbox_enabled ? 1 : 0
  name        = "${local.name_prefix}-jumpbox"
  description = "SSM jumpbox SG (no inbound); used for local port-forward to RDS"
  vpc_id      = var.vpc_id

  egress {
    description = "All egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_iam_role" "jumpbox" {
  count = var.jumpbox_enabled ? 1 : 0
  name  = "${local.name_prefix}-jumpbox-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "jumpbox_ssm" {
  count      = var.jumpbox_enabled ? 1 : 0
  role       = aws_iam_role.jumpbox[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "jumpbox" {
  count = var.jumpbox_enabled ? 1 : 0
  name  = "${local.name_prefix}-jumpbox-profile"
  role  = aws_iam_role.jumpbox[0].name
  tags  = local.tags
}

resource "aws_instance" "jumpbox" {
  count         = var.jumpbox_enabled ? 1 : 0
  ami           = data.aws_ami.al2023.id
  instance_type = "t4g.nano"
  subnet_id     = var.jumpbox_subnet_id

  vpc_security_group_ids = [
    aws_security_group.jumpbox[0].id,
    aws_security_group.db.id, # so this instance can reach DB without widening CIDRs
  ]

  iam_instance_profile = aws_iam_instance_profile.jumpbox[0].name

  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.tags, { "Name" = "${local.name_prefix}-jumpbox" })
}


