# PlanMod AWS Infrastructure
# Terraform configuration for cloud deployment

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Configure backend in terraform.tfvars or via environment
    # bucket = "planmod-terraform-state"
    # key    = "terraform.tfstate"
    # region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "planmod"
}

variable "vlm_api_key_secret_name" {
  description = "Name of AWS Secrets Manager secret for VLM API key"
  type        = string
  default     = "planmod/vlm-api-key"
}

# S3 Buckets
resource "aws_s3_bucket" "drawings" {
  bucket = "${var.project_name}-drawings-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name        = "${var.project_name}-drawings"
    Environment = "production"
  }
}

resource "aws_s3_bucket_versioning" "drawings" {
  bucket = aws_s3_bucket.drawings.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "processed" {
  bucket = "${var.project_name}-processed-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name        = "${var.project_name}-processed"
    Environment = "production"
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = [
          "${aws_s3_bucket.drawings.arn}/*",
          "${aws_s3_bucket.processed.arn}/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.vlm_api_key_secret_name}*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
    ]
  })
}

# Lambda function for ingestion
resource "aws_lambda_function" "ingestion" {
  filename         = "ingestion.zip"
  function_name    = "${var.project_name}-ingestion"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_handler.ingestion_handler"
  runtime         = "python3.11"
  timeout         = 300
  memory_size     = 512
  
  environment {
    variables = {
      DRAWINGS_BUCKET = aws_s3_bucket.drawings.bucket
      PROCESSED_BUCKET = aws_s3_bucket.processed.bucket
    }
  }
  
  # Note: Lambda deployment package should be built separately
  # This is a placeholder - actual deployment would use terraform apply with built zip
}

# Lambda function for VLM processing
resource "aws_lambda_function" "vlm_processor" {
  filename         = "vlm_processor.zip"
  function_name    = "${var.project_name}-vlm-processor"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_handler.vlm_handler"
  runtime         = "python3.11"
  timeout         = 900  # 15 minutes for VLM calls
  memory_size     = 1024
  
  environment {
    variables = {
      VLM_API_KEY_SECRET = var.vlm_api_key_secret_name
      PROCESSED_BUCKET = aws_s3_bucket.processed.bucket
    }
  }
}

# API Gateway
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE"]
    allow_headers = ["*"]
  }
}

resource "aws_apigatewayv2_integration" "ingestion" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.ingestion.invoke_arn
}

resource "aws_apigatewayv2_route" "upload" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /upload"
  target    = "integrations/${aws_apigatewayv2_integration.ingestion.id}"
}

resource "aws_lambda_permission" "api_gw_ingestion" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# ECS/Fargate for VLM service (if using self-hosted VLM)
resource "aws_ecs_cluster" "vlm_cluster" {
  name = "${var.project_name}-vlm-cluster"
}

resource "aws_ecs_task_definition" "vlm_service" {
  family                   = "${var.project_name}-vlm"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "2048"  # 2 vCPU
  memory                   = "4096"  # 4 GB
  
  container_definitions = jsonencode([
    {
      name  = "vlm-service"
      image = "planmod/vlm-service:latest"  # Custom image
      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "VLM_MODEL"
          value = "molmo-7b"  # Example
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}-vlm"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "vlm" {
  name              = "/ecs/${var.project_name}-vlm"
  retention_in_days = 7
}

# Data sources
data "aws_caller_identity" "current" {}

# Outputs
output "api_endpoint" {
  value = aws_apigatewayv2_api.api.api_endpoint
}

output "drawings_bucket" {
  value = aws_s3_bucket.drawings.bucket
}

output "processed_bucket" {
  value = aws_s3_bucket.processed.bucket
}

