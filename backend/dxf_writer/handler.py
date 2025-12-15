"""
Main handler for DXF writer module.
"""

import io
import logging
from typing import Any, Optional

from backend.shared.config import get_settings
from backend.shared.models import Job, JobStatus, SceneGraph, S3Reference
from backend.shared.s3_client import S3Client, get_s3_client
from backend.shared.dynamo_client import get_dynamo_client
from backend.dxf_writer.writer import DXFWriter

logger = logging.getLogger(__name__)


class DXFWriterHandler:
    """
    Main handler for DXF generation.
    """
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        settings: Optional[Any] = None,
    ):
        self.s3_client = s3_client or get_s3_client()
        self.settings = settings or get_settings()
        self.writer = DXFWriter()
    
    def generate(
        self,
        job: Job,
        scene_graph: SceneGraph,
    ) -> Job:
        """
        Generate DXF file from scene graph.
        
        Args:
            job: Associated job
            scene_graph: Scene graph to convert
            
        Returns:
            Updated job with DXF reference
        """
        logger.info(f"Generating DXF for job {job.id}")
        
        job.update_status(JobStatus.GENERATING_DXF, "generating_dxf", 85)
        
        # Generate DXF
        dxf_bytes = self.writer.write(scene_graph)
        
        # Upload to S3
        dxf_key = S3Client.generate_output_key(job.id, "base.dxf")
        self.s3_client.upload_bytes(
            dxf_bytes,
            dxf_key,
            content_type="application/dxf",
        )
        
        job.output.base_dxf = S3Reference(
            bucket=self.s3_client.bucket_name,
            key=dxf_key,
        )
        
        job.update_status(JobStatus.GENERATING_DXF, "dxf_complete", 90)
        
        logger.info(f"DXF generated: {len(dxf_bytes)} bytes")
        
        return job


# Lambda handler
def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point."""
    job_id = event.get("job_id")
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}
    
    dynamo = get_dynamo_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        return {"status": "error", "message": f"Job not found: {job_id}"}
    
    scene_graph = dynamo.get_scene_graph_by_job(job_id)
    if not scene_graph:
        return {"status": "error", "message": "Scene graph not found"}
    
    try:
        handler = DXFWriterHandler()
        job = handler.generate(job, scene_graph)
        dynamo.update_job(job)
        
        return {
            "status": "success",
            "job_id": job_id,
            "dxf_key": job.output.base_dxf.key if job.output.base_dxf else None,
        }
        
    except Exception as e:
        job.set_error(str(e))
        dynamo.update_job(job)
        return {"status": "error", "message": str(e)}


