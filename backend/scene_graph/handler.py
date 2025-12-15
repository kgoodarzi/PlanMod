"""
Main handler for scene graph module.
"""

import logging
from typing import Any, Optional

from backend.shared.config import get_settings
from backend.shared.models import Job, JobStatus, SceneGraph
from backend.shared.s3_client import S3Client, get_s3_client
from backend.shared.dynamo_client import DynamoDBClient, get_dynamo_client
from backend.scene_graph.graph_builder import GraphBuilder
from backend.scene_graph.renderer import SceneGraphRenderer

logger = logging.getLogger(__name__)


class SceneGraphHandler:
    """
    Main handler for scene graph operations.
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
        
        self.graph_builder = GraphBuilder()
        self.renderer = SceneGraphRenderer()
    
    def build_and_save(
        self,
        job: Job,
        scene_graph: SceneGraph,
    ) -> tuple[Job, SceneGraph]:
        """
        Finalize and save scene graph.
        
        Args:
            job: Associated job
            scene_graph: Scene graph to finalize
            
        Returns:
            Updated job and scene graph
        """
        logger.info(f"Finalizing scene graph for job {job.id}")
        
        job.update_status(JobStatus.BUILDING_GRAPH, "building_scene_graph", 75)
        
        # Build relationships
        scene_graph = self.graph_builder.build_relationships(scene_graph)
        
        # Assign DXF layers/names
        scene_graph = self.graph_builder.assign_dxf_mapping(scene_graph)
        
        # Save scene graph JSON to S3
        graph_json_key = S3Client.generate_output_key(job.id, "scene_graph.json")
        self.s3_client.upload_json(
            scene_graph.model_dump(),
            graph_json_key,
        )
        scene_graph_json_ref = self.s3_client.s3_client = None  # Reset for clean ref
        
        from backend.shared.models import S3Reference
        job.output.scene_graph_json = S3Reference(
            bucket=self.s3_client.bucket_name,
            key=graph_json_key,
        )
        
        # Render visualization
        try:
            vis_image = self.renderer.render(scene_graph)
            vis_key = S3Client.generate_output_key(job.id, "scene_graph.png")
            
            from PIL import Image
            import io
            
            pil_image = Image.fromarray(vis_image)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            
            self.s3_client.upload_bytes(
                buffer.getvalue(),
                vis_key,
                content_type="image/png",
            )
            
            job.output.scene_graph_image = S3Reference(
                bucket=self.s3_client.bucket_name,
                key=vis_key,
            )
        except Exception as e:
            logger.warning(f"Failed to render scene graph visualization: {e}")
        
        # Save to DynamoDB
        self.dynamo_client.update_scene_graph(scene_graph)
        
        job.scene_graph_id = scene_graph.id
        job.update_status(JobStatus.BUILDING_GRAPH, "scene_graph_complete", 80)
        
        self.dynamo_client.update_job(job)
        
        logger.info(f"Scene graph finalized: {len(scene_graph.views)} views, "
                   f"{len(scene_graph.components)} components")
        
        return job, scene_graph
    
    def get_summary(self, scene_graph: SceneGraph) -> dict:
        """Get a summary of the scene graph for display/LLM."""
        return {
            "id": scene_graph.id,
            "title": scene_graph.title,
            "views": [
                {
                    "id": v.id,
                    "name": v.name,
                    "type": v.view_type.value,
                    "component_count": len(v.component_ids),
                }
                for v in scene_graph.views
            ],
            "components": [
                {
                    "id": c.id,
                    "name": c.name,
                    "type": c.component_type.value,
                    "confidence": c.classification_confidence,
                }
                for c in scene_graph.components
            ],
            "total_entities": len(scene_graph.entities),
            "uncertainties": scene_graph.uncertainties,
        }


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
        handler = SceneGraphHandler()
        job, scene_graph = handler.build_and_save(job, scene_graph)
        
        return {
            "status": "success",
            "job_id": job_id,
            "scene_graph_id": scene_graph.id,
        }
        
    except Exception as e:
        job.set_error(str(e))
        dynamo.update_job(job)
        return {"status": "error", "message": str(e)}


