# Variable definitions for PlanMod infrastructure

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

