data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ssm_tunnel" {
  count              = var.enable_ssm_tunnel ? 1 : 0
  name               = "${var.name_prefix}-ssm-tunnel"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ssm_tunnel_core" {
  count      = var.enable_ssm_tunnel ? 1 : 0
  role       = aws_iam_role.ssm_tunnel[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm_tunnel" {
  count = var.enable_ssm_tunnel ? 1 : 0
  name  = "${var.name_prefix}-ssm-tunnel"
  role  = aws_iam_role.ssm_tunnel[0].name
}

resource "aws_security_group" "ssm_tunnel" {
  count       = var.enable_ssm_tunnel ? 1 : 0
  name        = "${var.name_prefix}-ssm-tunnel"
  description = "SSM tunnel instance (no inbound; used only for SSM port-forwarding)"
  vpc_id      = var.vpc_id

  # No ingress rules on purpose.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ami" "al2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-6.1-arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "ssm_tunnel" {
  count                = var.enable_ssm_tunnel ? 1 : 0
  ami                  = data.aws_ami.al2023_arm64.id
  instance_type        = var.ssm_tunnel_instance_type
  subnet_id            = var.ssm_tunnel_subnet_id
  iam_instance_profile = aws_iam_instance_profile.ssm_tunnel[0].name
  vpc_security_group_ids = [
    aws_security_group.ssm_tunnel[0].id,
  ]

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  tags = {
    Name = "${var.name_prefix}-ssm-tunnel"
  }
}


