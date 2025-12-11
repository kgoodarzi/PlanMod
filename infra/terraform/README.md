# PlanMod AWS Infrastructure

Terraform configuration for deploying PlanMod to AWS.

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- AWS account with permissions to create:
  - S3 buckets
  - Lambda functions
  - API Gateway
  - IAM roles and policies
  - ECS/Fargate (if using self-hosted VLM)

## Setup

1. Configure backend (optional):
   ```bash
   # Create S3 bucket for Terraform state
   aws s3 mb s3://planmod-terraform-state
   ```

2. Set variables:
   ```bash
   # Create terraform.tfvars
   aws_region = "us-east-1"
   project_name = "planmod"
   vlm_api_key_secret_name = "planmod/vlm-api-key"
   ```

3. Store VLM API key in Secrets Manager:
   ```bash
   aws secretsmanager create-secret \
     --name planmod/vlm-api-key \
     --secret-string "your-api-key-here"
   ```

4. Initialize Terraform:
   ```bash
   terraform init
   ```

5. Plan and apply:
   ```bash
   terraform plan
   terraform apply
   ```

## Architecture

- **S3 Buckets**: Storage for raw and processed drawings
- **Lambda Functions**: Serverless processing (ingestion, VLM calls)
- **API Gateway**: HTTP API for upload and status
- **ECS/Fargate**: Optional self-hosted VLM service
- **IAM Roles**: Least-privilege access policies

## Notes

- Lambda deployment packages need to be built separately
- VLM service container image needs to be built and pushed to ECR
- For MVP, prefer managed VLM APIs (Claude, GPT-4 Vision) over self-hosted

