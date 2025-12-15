"""
Main orchestration handler.
"""

import asyncio
import logging
from typing import Any, Optional

from backend.shared.config import get_settings
from backend.shared.models import Job, JobStatus, SceneGraph
from backend.shared.s3_client import S3Client, get_s3_client
from backend.shared.dynamo_client import DynamoDBClient, get_dynamo_client

from backend.ingest import IngestHandler
from backend.vision import VisionHandler
from backend.vectorization import VectorizationHandler
from backend.scene_graph import SceneGraphHandler
from backend.dxf_writer import DXFWriterHandler
from backend.transform import TransformHandler

logger = logging.getLogger(__name__)


class OrchestrationHandler:
    """
    Orchestrates the complete processing pipeline.
    
    Steps:
    1. Ingest: Normalize input file
    2. Vision: Analyze with CV and VLM
    3. Vectorization: Convert to vector geometry
    4. Scene Graph: Build semantic model
    5. DXF Writer: Generate base DXF
    6. Transform: Apply substitutions and generate final DXF
    """
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        dynamo_client: Optional[DynamoDBClient] = None,
        settings: Optional[Any] = None,
    ):
        self.s3_client = s3_client or get_s3_client()
        self.dynamo_client = dynamo_client or get_dynamo_client()
        self.settings = settings or get_settings()
        
        # Initialize handlers
        self.ingest_handler = IngestHandler(self.s3_client, self.settings)
        self.vision_handler = VisionHandler(self.s3_client)
        self.vectorization_handler = VectorizationHandler(self.settings)
        self.scene_graph_handler = SceneGraphHandler(self.s3_client, self.dynamo_client, self.settings)
        self.dxf_writer_handler = DXFWriterHandler(self.s3_client, self.settings)
        self.transform_handler = TransformHandler(self.s3_client, self.settings)
    
    async def process_job(self, job: Job) -> Job:
        """
        Process a job through the complete pipeline.
        
        Args:
            job: Job to process
            
        Returns:
            Completed job
        """
        logger.info(f"Starting pipeline for job {job.id}")
        
        try:
            # Step 1: Ingest
            logger.info("Step 1: Ingesting input file")
            job = self.ingest_handler.process(job)
            self.dynamo_client.update_job(job)
            
            # Step 2: Vision Analysis
            logger.info("Step 2: Running vision analysis")
            job, scene_graph = await self.vision_handler.analyze(job)
            self.dynamo_client.update_job(job)
            self.dynamo_client.create_scene_graph(scene_graph)
            job.scene_graph_id = scene_graph.id
            
            # Step 3: Vectorization
            logger.info("Step 3: Vectorizing image")
            # Load image
            from PIL import Image
            import io
            import numpy as np
            
            image_bytes = self.s3_client.download_bytes(job.output.normalized_image.key)
            image = np.array(Image.open(io.BytesIO(image_bytes)))
            
            scene_graph = self.vectorization_handler.vectorize(image, scene_graph)
            job.update_status(JobStatus.VECTORIZING, "vectorization_complete", 70)
            self.dynamo_client.update_job(job)
            self.dynamo_client.update_scene_graph(scene_graph)
            
            # Step 4: Scene Graph Finalization
            logger.info("Step 4: Building scene graph")
            job, scene_graph = self.scene_graph_handler.build_and_save(job, scene_graph)
            
            # Step 5: DXF Generation
            logger.info("Step 5: Generating base DXF")
            job = self.dxf_writer_handler.generate(job, scene_graph)
            self.dynamo_client.update_job(job)
            
            # Step 6: Transform (if rules provided)
            if job.substitution_rules:
                logger.info("Step 6: Applying transformations")
                job = self.transform_handler.transform(job, scene_graph)
            else:
                # Copy base to final
                logger.info("Step 6: No substitutions, copying base to final")
                job = self.transform_handler.transform(job, scene_graph, [])
            
            self.dynamo_client.update_job(job)
            
            logger.info(f"Pipeline complete for job {job.id}")
            
            return job
            
        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {e}")
            job.set_error(str(e))
            self.dynamo_client.update_job(job)
            raise
    
    def process_job_sync(self, job: Job) -> Job:
        """Synchronous wrapper for process_job."""
        return asyncio.run(self.process_job(job))


# Lambda handler for Step Functions
def lambda_handler(event: dict, context: Any) -> dict:
    """
    AWS Lambda entry point for orchestration.
    
    This handler is designed for Step Functions integration.
    """
    action = event.get("action", "process")
    job_id = event.get("job_id")
    
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}
    
    dynamo = get_dynamo_client()
    job = dynamo.get_job(job_id)
    
    if not job:
        return {"status": "error", "message": f"Job not found: {job_id}"}
    
    handler = OrchestrationHandler()
    
    try:
        if action == "process":
            job = handler.process_job_sync(job)
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
        
        return {
            "status": "success",
            "job_id": job.id,
            "job_status": job.status.value,
            "outputs": {
                "base_dxf": job.output.base_dxf.key if job.output.base_dxf else None,
                "final_dxf": job.output.final_dxf.key if job.output.final_dxf else None,
                "report": job.output.report.key if job.output.report else None,
            },
        }
        
    except Exception as e:
        return {
            "status": "error",
            "job_id": job_id,
            "message": str(e),
        }


