#!/usr/bin/env python3
"""
AWS CDK Application for PlanMod.

Deploys the complete serverless infrastructure.
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import aws_cdk as cdk

from backend.shared.config import get_settings
from infrastructure.cdk.stacks.storage_stack import StorageStack
from infrastructure.cdk.stacks.compute_stack import ComputeStack
from infrastructure.cdk.stacks.api_stack import ApiStack


def main():
    """Create CDK app and stacks."""
    settings = get_settings()
    
    app = cdk.App()
    
    env = cdk.Environment(
        account=settings.deployment.account_id or os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=settings.aws.region,
    )
    
    prefix = settings.deployment.stack_prefix
    environment = settings.deployment.environment
    
    # Storage stack (S3, DynamoDB)
    storage_stack = StorageStack(
        app,
        f"{prefix}-storage-{environment}",
        env=env,
        settings=settings,
    )
    
    # Compute stack (Lambda functions)
    compute_stack = ComputeStack(
        app,
        f"{prefix}-compute-{environment}",
        env=env,
        settings=settings,
        storage_stack=storage_stack,
    )
    
    # API stack (API Gateway)
    api_stack = ApiStack(
        app,
        f"{prefix}-api-{environment}",
        env=env,
        settings=settings,
        compute_stack=compute_stack,
    )
    
    # Add tags to all resources
    for key, value in settings.cost.tags.items():
        cdk.Tags.of(app).add(key, value)
    
    app.synth()


if __name__ == "__main__":
    main()


