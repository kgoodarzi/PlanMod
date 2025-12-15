"""
Storage Stack - S3 and DynamoDB resources.
"""

from typing import Any

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class StorageStack(Stack):
    """
    Creates storage resources:
    - S3 bucket for file storage
    - DynamoDB tables for job and scene graph data
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        settings: Any,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.settings = settings
        prefix = settings.deployment.stack_prefix
        env = settings.deployment.environment
        
        # S3 Bucket
        self.bucket = s3.Bucket(
            self,
            "StorageBucket",
            bucket_name=f"{prefix}-storage-{env}",
            versioned=settings.storage.versioning_enabled,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.POST,
                    ],
                    allowed_origins=settings.api.cors_origins,
                    allowed_headers=["*"],
                    max_age=3600,
                )
            ],
            lifecycle_rules=[
                # Delete temp files after retention period
                s3.LifecycleRule(
                    id="DeleteTempFiles",
                    prefix="temp/",
                    expiration=Duration.days(settings.storage.temp_retention_days),
                ),
            ],
            removal_policy=RemovalPolicy.DESTROY if env == "dev" else RemovalPolicy.RETAIN,
            auto_delete_objects=env == "dev",
        )
        
        # DynamoDB Tables
        
        # Jobs table
        self.jobs_table = dynamodb.Table(
            self,
            "JobsTable",
            table_name=f"{prefix}-jobs-{env}",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
            if settings.dynamodb.billing_mode == "PAY_PER_REQUEST"
            else dynamodb.BillingMode.PROVISIONED,
            point_in_time_recovery=settings.dynamodb.point_in_time_recovery,
            removal_policy=RemovalPolicy.DESTROY if env == "dev" else RemovalPolicy.RETAIN,
        )
        
        # Add GSI for status queries
        self.jobs_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING,
            ),
        )
        
        # Scene graphs table
        self.scene_graphs_table = dynamodb.Table(
            self,
            "SceneGraphsTable",
            table_name=f"{prefix}-scene-graphs-{env}",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
            if settings.dynamodb.billing_mode == "PAY_PER_REQUEST"
            else dynamodb.BillingMode.PROVISIONED,
            point_in_time_recovery=settings.dynamodb.point_in_time_recovery,
            removal_policy=RemovalPolicy.DESTROY if env == "dev" else RemovalPolicy.RETAIN,
        )
        
        # Add GSI for job_id queries
        self.scene_graphs_table.add_global_secondary_index(
            index_name="job-index",
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING,
            ),
        )


