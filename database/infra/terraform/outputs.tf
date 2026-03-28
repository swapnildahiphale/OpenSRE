output "db_endpoint" {
  value       = aws_db_instance.db.address
  description = "RDS endpoint hostname"
}

output "db_port" {
  value       = aws_db_instance.db.port
  description = "RDS port"
}

output "db_name" {
  value       = var.db_name
  description = "Database name"
}

output "db_security_group_id" {
  value       = aws_security_group.db.id
  description = "Security group ID for the DB"
}

output "db_secret_arn" {
  value       = aws_secretsmanager_secret.db.arn
  description = "Secrets Manager ARN containing DB connection info"
}

output "jumpbox_instance_id" {
  value       = try(aws_instance.jumpbox[0].id, null)
  description = "SSM jumpbox instance ID (for port-forward). Null if disabled."
}


