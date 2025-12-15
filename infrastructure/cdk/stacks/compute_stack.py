"""
Compute Stack - Lambda functions and Step Functions.
"""

from typing import Any

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct


class ComputeStack(Stack):
    """
    Creates compute resources:
    - Lambda functions for each pipeline stage
    - Step Functions state machine for orchestration
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        settings: Any,
        storage_stack: Any,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.settings = settings
        self.storage_stack = storage_stack
        prefix = settings.deployment.stack_prefix
        env = settings.deployment.environment
        
        # Common Lambda configuration
        lambda_timeout = Duration.seconds(settings.lambda_config.timeout_seconds)
        lambda_memory = settings.lambda_config.memory_mb
        
        # Common environment variables
        common_env = {
            "PLANMOD_AWS__REGION": settings.aws.region,
            "PLANMOD_DEPLOYMENT__ENVIRONMENT": env,
            "PLANMOD_DEPLOYMENT__STACK_PREFIX": prefix,
            "BUCKET_NAME": storage_stack.bucket.bucket_name,
            "JOBS_TABLE": storage_stack.jobs_table.table_name,
            "SCENE_GRAPHS_TABLE": storage_stack.scene_graphs_table.table_name,
        }
        
        # IAM role for Lambda functions
        lambda_role = iam.Role(
            self,
            "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
            ],
        )
        
        # Grant permissions
        storage_stack.bucket.grant_read_write(lambda_role)
        storage_stack.jobs_table.grant_read_write_data(lambda_role)
        storage_stack.scene_graphs_table.grant_read_write_data(lambda_role)
        
        # Bedrock permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )
        
        # Textract permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "textract:DetectDocumentText",
                    "textract:AnalyzeDocument",
                ],
                resources=["*"],
            )
        )
        
        # Create Lambda functions
        
        # Ingest function
        self.ingest_fn = lambda_.Function(
            self,
            "IngestFunction",
            function_name=f"{prefix}-ingest-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.ingest.handler.lambda_handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=lambda_timeout,
            memory_size=lambda_memory,
            role=lambda_role,
            environment=common_env,
        )
        
        # Vision function
        self.vision_fn = lambda_.Function(
            self,
            "VisionFunction",
            function_name=f"{prefix}-vision-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.vision.handler.lambda_handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=lambda_timeout,
            memory_size=lambda_memory,
            role=lambda_role,
            environment=common_env,
        )
        
        # Vectorization function
        self.vectorization_fn = lambda_.Function(
            self,
            "VectorizationFunction",
            function_name=f"{prefix}-vectorization-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.vectorization.handler.lambda_handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=lambda_timeout,
            memory_size=lambda_memory,
            role=lambda_role,
            environment=common_env,
        )
        
        # Scene graph function
        self.scene_graph_fn = lambda_.Function(
            self,
            "SceneGraphFunction",
            function_name=f"{prefix}-scene-graph-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.scene_graph.handler.lambda_handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=lambda_timeout,
            memory_size=lambda_memory,
            role=lambda_role,
            environment=common_env,
        )
        
        # DXF writer function
        self.dxf_writer_fn = lambda_.Function(
            self,
            "DXFWriterFunction",
            function_name=f"{prefix}-dxf-writer-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.dxf_writer.handler.lambda_handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=lambda_timeout,
            memory_size=lambda_memory,
            role=lambda_role,
            environment=common_env,
        )
        
        # Transform function
        self.transform_fn = lambda_.Function(
            self,
            "TransformFunction",
            function_name=f"{prefix}-transform-{env}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="backend.transform.handler.lambda_handler",
            code=lambda_.Code.from_asset("../../"),
            timeout=lambda_timeout,
            memory_size=lambda_memory,
            role=lambda_role,
            environment=common_env,
        )
        
        # Create Step Functions state machine
        self._create_state_machine(prefix, env)
    
    def _create_state_machine(self, prefix: str, env: str):
        """Create Step Functions state machine for pipeline orchestration."""
        
        # Define tasks
        ingest_task = tasks.LambdaInvoke(
            self,
            "IngestTask",
            lambda_function=self.ingest_fn,
            output_path="$.Payload",
        )
        
        vision_task = tasks.LambdaInvoke(
            self,
            "VisionTask",
            lambda_function=self.vision_fn,
            output_path="$.Payload",
        )
        
        vectorization_task = tasks.LambdaInvoke(
            self,
            "VectorizationTask",
            lambda_function=self.vectorization_fn,
            output_path="$.Payload",
        )
        
        scene_graph_task = tasks.LambdaInvoke(
            self,
            "SceneGraphTask",
            lambda_function=self.scene_graph_fn,
            output_path="$.Payload",
        )
        
        dxf_writer_task = tasks.LambdaInvoke(
            self,
            "DXFWriterTask",
            lambda_function=self.dxf_writer_fn,
            output_path="$.Payload",
        )
        
        transform_task = tasks.LambdaInvoke(
            self,
            "TransformTask",
            lambda_function=self.transform_fn,
            output_path="$.Payload",
        )
        
        # Define state machine
        definition = (
            ingest_task
            .next(vision_task)
            .next(vectorization_task)
            .next(scene_graph_task)
            .next(dxf_writer_task)
            .next(transform_task)
        )
        
        self.state_machine = sfn.StateMachine(
            self,
            "PipelineStateMachine",
            state_machine_name=f"{prefix}-pipeline-{env}",
            definition=definition,
            timeout=Duration.hours(1),
        )


