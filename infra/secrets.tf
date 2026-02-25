resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.project_name}/${var.environment}/openai-api-key"
  recovery_window_in_days = 0

  tags = { Name = "${var.project_name}-openai-key" }
}

# Do NOT set the secret value in Terraform. After `terraform apply`, run:
#   aws secretsmanager put-secret-value \
#     --secret-id supplier-negotiation/prod/openai-api-key \
#     --secret-string '{"OPENAI_API_KEY":"sk-..."}'
