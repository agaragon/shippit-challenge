variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "supplier-negotiation"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "task_cpu" {
  type    = number
  default = 512
}

variable "task_memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "model_name" {
  type    = string
  default = "gpt-4o"
}

variable "domain_name" {
  type    = string
  default = ""
}

variable "hosted_zone_domain" {
  description = "Root domain for the Route 53 hosted zone (e.g. programmingwitharagon.com)"
  type        = string
  default     = ""
}

locals {
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
