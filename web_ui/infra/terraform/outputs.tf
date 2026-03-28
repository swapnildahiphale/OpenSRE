output "alb_dns_name" {
  value       = aws_lb.app.dns_name
  description = "ALB DNS name to access the service"
}

output "alb_arn" {
  value       = aws_lb.app.arn
  description = "ALB ARN"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.app.repository_url
  description = "ECR repository URL (created for convenience)"
}

output "ssm_tunnel_instance_id" {
  value       = var.enable_ssm_tunnel ? aws_instance.ssm_tunnel[0].id : null
  description = "Instance ID for SSM port-forward tunnel (null if disabled)"
}

output "ssm_port_forward_command_http" {
  value = var.enable_ssm_tunnel ? join(
    "",
    [
      "aws ssm start-session ",
      "--target ", aws_instance.ssm_tunnel[0].id, " ",
      "--document-name AWS-StartPortForwardingSessionToRemoteHost ",
      "--parameters ",
      "'{\"host\":[\"", aws_lb.app.dns_name, "\"],\"portNumber\":[\"80\"],\"localPortNumber\":[\"8081\"]}'",
    ],
  ) : null
  description = "Command to port-forward localhost:8081 -> internal ALB:80 via SSM tunnel instance (requires awscli + session-manager-plugin)."
}


