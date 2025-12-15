"""
Workflow management for Step Functions.
"""

import json
import logging
from typing import Any, Optional

import boto3

from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class WorkflowManager:
    """
    Manages AWS Step Functions workflows.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self._client: Optional[Any] = None
    
    @property
    def client(self) -> Any:
        """Get or create Step Functions client."""
        if self._client is None:
            config = self.settings.get_boto3_config()
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._client = session.client("stepfunctions", **config)
            else:
                self._client = boto3.client("stepfunctions", **config)
        
        return self._client
    
    def start_execution(
        self,
        state_machine_arn: str,
        job_id: str,
        input_data: Optional[dict] = None,
    ) -> str:
        """
        Start a Step Functions execution.
        
        Args:
            state_machine_arn: ARN of state machine
            job_id: Job ID to process
            input_data: Additional input data
            
        Returns:
            Execution ARN
        """
        execution_input = {
            "job_id": job_id,
            **(input_data or {}),
        }
        
        response = self.client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"planmod-{job_id}",
            input=json.dumps(execution_input),
        )
        
        logger.info(f"Started execution: {response['executionArn']}")
        
        return response["executionArn"]
    
    def get_execution_status(self, execution_arn: str) -> dict:
        """
        Get status of a Step Functions execution.
        
        Args:
            execution_arn: Execution ARN
            
        Returns:
            Execution status
        """
        response = self.client.describe_execution(
            executionArn=execution_arn,
        )
        
        return {
            "status": response["status"],
            "start_date": response.get("startDate"),
            "stop_date": response.get("stopDate"),
            "output": json.loads(response.get("output", "{}")) if response.get("output") else None,
            "error": response.get("error"),
            "cause": response.get("cause"),
        }
    
    def stop_execution(self, execution_arn: str, cause: str = "User requested stop") -> bool:
        """
        Stop a running execution.
        
        Args:
            execution_arn: Execution ARN
            cause: Reason for stopping
            
        Returns:
            True if stopped successfully
        """
        try:
            self.client.stop_execution(
                executionArn=execution_arn,
                cause=cause,
            )
            logger.info(f"Stopped execution: {execution_arn}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop execution: {e}")
            return False


