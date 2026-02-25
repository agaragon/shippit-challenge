terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # To use S3 remote state, bootstrap the bucket and table first:
  #   aws s3api create-bucket --bucket supplier-negotiation-tf-state --region us-east-1
  #   aws dynamodb create-table --table-name supplier-negotiation-tf-lock \
  #     --attribute-definitions AttributeName=LockID,AttributeType=S \
  #     --key-schema AttributeName=LockID,KeyType=HASH \
  #     --billing-mode PAY_PER_REQUEST
  #
  # Then uncomment:
  # backend "s3" {
  #   bucket         = "supplier-negotiation-tf-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "supplier-negotiation-tf-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.tags
  }
}
