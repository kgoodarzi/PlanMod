"""
API Stack - API Gateway resources.
"""

from typing import Any

from aws_cdk import (
    Stack,
    Duration,
    aws_apigateway as apigw,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct


class ApiStack(Stack):
    """
    Creates API Gateway resources:
    - REST API
    - Lambda integration
    - API key authentication
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        settings: Any,
        compute_stack: Any,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.settings = settings
        prefix = settings.deployment.stack_prefix
        env = settings.deployment.environment
        
        # Create API handler Lambda
        api_handler = lambda_.Function(
            self,
            "ApiHandler",
            function_name=f"{prefix}-api-handler-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.api.lambda_handler.handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "PLANMOD_AWS__REGION": settings.aws.region,
                "PLANMOD_DEPLOYMENT__ENVIRONMENT": env,
                "PLANMOD_DEPLOYMENT__STACK_PREFIX": prefix,
            },
        )
        
        # Create REST API
        self.api = apigw.RestApi(
            self,
            "PlanModApi",
            rest_api_name=f"{prefix}-api-{env}",
            description="PlanMod Drawing to DXF API",
            deploy_options=apigw.StageOptions(
                stage_name=env,
                throttling_rate_limit=settings.api.rate_limit,
                throttling_burst_limit=settings.api.burst_limit,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=settings.api.cors_origins,
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["*"],
            ) if settings.api.cors_enabled else None,
        )
        
        # Lambda integration
        lambda_integration = apigw.LambdaIntegration(
            api_handler,
            request_templates={"application/json": '{ "statusCode": "200" }'},
        )
        
        # Add resources and methods
        
        # /jobs
        jobs_resource = self.api.root.add_resource("jobs")
        jobs_resource.add_method("GET", lambda_integration)  # List jobs
        jobs_resource.add_method("POST", lambda_integration)  # Create job
        
        # /jobs/{id}
        job_resource = jobs_resource.add_resource("{job_id}")
        job_resource.add_method("GET", lambda_integration)  # Get job status
        
        # /jobs/{id}/upload
        upload_resource = job_resource.add_resource("upload")
        upload_resource.add_method("POST", lambda_integration)  # Upload file
        
        # /jobs/{id}/process
        process_resource = job_resource.add_resource("process")
        process_resource.add_method("POST", lambda_integration)  # Start processing
        
        # /jobs/{id}/scene-graph
        scene_graph_resource = job_resource.add_resource("scene-graph")
        scene_graph_resource.add_method("GET", lambda_integration)  # Get scene graph
        
        # /jobs/{id}/substitute
        substitute_resource = job_resource.add_resource("substitute")
        substitute_resource.add_method("POST", lambda_integration)  # Apply substitutions
        
        # /jobs/{id}/download/{file_type}
        download_resource = job_resource.add_resource("download")
        download_file_resource = download_resource.add_resource("{file_type}")
        download_file_resource.add_method("GET", lambda_integration)  # Download file
        
        # /components
        components_resource = self.api.root.add_resource("components")
        components_resource.add_method("GET", lambda_integration)  # List components
        
        # API Key (if enabled)
        if settings.api.auth_type == "API_KEY":
            api_key = self.api.add_api_key(
                "PlanModApiKey",
                api_key_name=f"{prefix}-api-key-{env}",
            )
            
            usage_plan = self.api.add_usage_plan(
                "UsagePlan",
                name=f"{prefix}-usage-plan-{env}",
                throttle=apigw.ThrottleSettings(
                    rate_limit=settings.api.rate_limit,
                    burst_limit=settings.api.burst_limit,
                ),
            )
            
            usage_plan.add_api_key(api_key)
            usage_plan.add_api_stage(stage=self.api.deployment_stage)


