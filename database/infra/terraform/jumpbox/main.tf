provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

locals {
  tags = merge({ Project = var.project }, var.tags)
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }
}

resource "aws_security_group" "jumpbox" {
  name_prefix = "${var.project}-jumpbox-"
  description = "SSM jumpbox SG (no inbound)"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_iam_role" "jumpbox" {
  name_prefix = "${var.project}-jumpbox-role-"

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

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.jumpbox.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "jumpbox" {
  name_prefix = "${var.project}-jumpbox-profile-"
  role = aws_iam_role.jumpbox.name
  tags = local.tags
}

resource "aws_instance" "jumpbox" {
  ami           = data.aws_ami.al2023.id
  instance_type = var.instance_type
  subnet_id     = var.subnet_id

  vpc_security_group_ids = [aws_security_group.jumpbox.id]
  iam_instance_profile   = aws_iam_instance_profile.jumpbox.name

  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.tags, { Name = "${var.project}-jumpbox" })
}


