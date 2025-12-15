# Outputs for PlanMod infrastructure

output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "drawings_bucket" {
  description = "S3 bucket for raw drawings"
  value       = aws_s3_bucket.drawings.bucket
}

output "processed_bucket" {
  description = "S3 bucket for processed drawings"
  value       = aws_s3_bucket.processed.bucket
}

