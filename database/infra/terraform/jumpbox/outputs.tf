output "jumpbox_instance_id" {
  value       = aws_instance.jumpbox.id
  description = "Instance ID for SSM port-forward"
}


