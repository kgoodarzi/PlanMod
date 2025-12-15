"""
DynamoDB client utilities for PlanMod.

Provides high-level operations for job and scene graph storage.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from backend.shared.config import get_settings
from backend.shared.models import Job, JobStatus, SceneGraph


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def decimal_default(obj: Any) -> Any:
    """Convert non-serializable types for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class DynamoDBClient:
    """
    High-level DynamoDB client for PlanMod operations.
    """
    
    # Table names (will be prefixed with stack name)
    JOBS_TABLE = "jobs"
    SCENE_GRAPHS_TABLE = "scene-graphs"
    
    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize DynamoDB client.
        
        Args:
            settings: Optional settings override
        """
        self.settings = settings or get_settings()
        self._client: Optional[Any] = None
        self._resource: Optional[Any] = None
    
    @property
    def client(self) -> Any:
        """Get or create boto3 DynamoDB client."""
        if self._client is None:
            config = self.settings.get_boto3_config()
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._client = session.client("dynamodb", **config)
            else:
                self._client = boto3.client("dynamodb", **config)
        
        return self._client
    
    @property
    def resource(self) -> Any:
        """Get or create boto3 DynamoDB resource."""
        if self._resource is None:
            config = self.settings.get_boto3_config()
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._resource = session.resource("dynamodb", **config)
            else:
                self._resource = boto3.resource("dynamodb", **config)
        
        return self._resource
    
    def _get_table_name(self, base_name: str) -> str:
        """Get full table name with prefix."""
        prefix = self.settings.deployment.stack_prefix
        env = self.settings.deployment.environment
        return f"{prefix}-{base_name}-{env}"
    
    @property
    def jobs_table_name(self) -> str:
        """Get jobs table name."""
        return self._get_table_name(self.JOBS_TABLE)
    
    @property
    def scene_graphs_table_name(self) -> str:
        """Get scene graphs table name."""
        return self._get_table_name(self.SCENE_GRAPHS_TABLE)
    
    def _serialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Serialize item for DynamoDB storage."""
        # Convert to JSON and back to handle special types
        json_str = json.dumps(item, default=decimal_default)
        return json.loads(json_str, parse_float=Decimal)
    
    def _deserialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Deserialize item from DynamoDB."""
        # Convert Decimals back to floats
        json_str = json.dumps(item, cls=DecimalEncoder)
        return json.loads(json_str)
    
    # =========================================================================
    # Job Operations
    # =========================================================================
    
    def create_job(self, job: Job) -> Job:
        """
        Create a new job in DynamoDB.
        
        Args:
            job: Job to create
            
        Returns:
            Created job
        """
        table = self.resource.Table(self.jobs_table_name)
        item = self._serialize_item(job.model_dump())
        
        table.put_item(Item=item)
        
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job if found, None otherwise
        """
        table = self.resource.Table(self.jobs_table_name)
        
        try:
            response = table.get_item(Key={"id": job_id})
            
            if "Item" not in response:
                return None
            
            item = self._deserialize_item(response["Item"])
            return Job(**item)
        
        except ClientError:
            return None
    
    def update_job(self, job: Job) -> Job:
        """
        Update an existing job.
        
        Args:
            job: Job with updated fields
            
        Returns:
            Updated job
        """
        job.updated_at = datetime.utcnow()
        
        table = self.resource.Table(self.jobs_table_name)
        item = self._serialize_item(job.model_dump())
        
        table.put_item(Item=item)
        
        return job
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        stage: str,
        progress: int = 0,
        error_message: Optional[str] = None,
    ) -> Optional[Job]:
        """
        Update job status fields only.
        
        Args:
            job_id: Job ID
            status: New status
            stage: Current processing stage
            progress: Progress percentage (0-100)
            error_message: Optional error message
            
        Returns:
            Updated job or None if not found
        """
        job = self.get_job(job_id)
        if job is None:
            return None
        
        job.update_status(status, stage, progress)
        if error_message:
            job.error_message = error_message
        
        return self.update_job(job)
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if deleted
        """
        table = self.resource.Table(self.jobs_table_name)
        
        try:
            table.delete_item(Key={"id": job_id})
            return True
        except ClientError:
            return False
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[Job]:
        """
        List jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs
        """
        table = self.resource.Table(self.jobs_table_name)
        
        if status:
            # Use scan with filter (not ideal for production)
            response = table.scan(
                FilterExpression="status = :status",
                ExpressionAttributeValues={":status": status.value},
                Limit=limit,
            )
        else:
            response = table.scan(Limit=limit)
        
        jobs = []
        for item in response.get("Items", []):
            item = self._deserialize_item(item)
            jobs.append(Job(**item))
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs
    
    # =========================================================================
    # Scene Graph Operations
    # =========================================================================
    
    def create_scene_graph(self, scene_graph: SceneGraph) -> SceneGraph:
        """
        Create a new scene graph in DynamoDB.
        
        Args:
            scene_graph: Scene graph to create
            
        Returns:
            Created scene graph
        """
        table = self.resource.Table(self.scene_graphs_table_name)
        item = self._serialize_item(scene_graph.model_dump())
        
        table.put_item(Item=item)
        
        return scene_graph
    
    def get_scene_graph(self, scene_graph_id: str) -> Optional[SceneGraph]:
        """
        Get a scene graph by ID.
        
        Args:
            scene_graph_id: Scene graph ID
            
        Returns:
            Scene graph if found, None otherwise
        """
        table = self.resource.Table(self.scene_graphs_table_name)
        
        try:
            response = table.get_item(Key={"id": scene_graph_id})
            
            if "Item" not in response:
                return None
            
            item = self._deserialize_item(response["Item"])
            return SceneGraph(**item)
        
        except ClientError:
            return None
    
    def get_scene_graph_by_job(self, job_id: str) -> Optional[SceneGraph]:
        """
        Get scene graph by job ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Scene graph if found, None otherwise
        """
        table = self.resource.Table(self.scene_graphs_table_name)
        
        # Scan for job_id (would use GSI in production)
        response = table.scan(
            FilterExpression="job_id = :job_id",
            ExpressionAttributeValues={":job_id": job_id},
            Limit=1,
        )
        
        items = response.get("Items", [])
        if not items:
            return None
        
        item = self._deserialize_item(items[0])
        return SceneGraph(**item)
    
    def update_scene_graph(self, scene_graph: SceneGraph) -> SceneGraph:
        """
        Update an existing scene graph.
        
        Args:
            scene_graph: Scene graph with updated fields
            
        Returns:
            Updated scene graph
        """
        scene_graph.updated_at = datetime.utcnow()
        
        table = self.resource.Table(self.scene_graphs_table_name)
        item = self._serialize_item(scene_graph.model_dump())
        
        table.put_item(Item=item)
        
        return scene_graph
    
    def delete_scene_graph(self, scene_graph_id: str) -> bool:
        """
        Delete a scene graph.
        
        Args:
            scene_graph_id: Scene graph ID
            
        Returns:
            True if deleted
        """
        table = self.resource.Table(self.scene_graphs_table_name)
        
        try:
            table.delete_item(Key={"id": scene_graph_id})
            return True
        except ClientError:
            return False


# Singleton instance
_dynamo_client: Optional[DynamoDBClient] = None


def get_dynamo_client() -> DynamoDBClient:
    """Get or create singleton DynamoDB client."""
    global _dynamo_client
    if _dynamo_client is None:
        _dynamo_client = DynamoDBClient()
    return _dynamo_client


