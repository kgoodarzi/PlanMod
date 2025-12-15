"""
Main handler for the vision module.

Orchestrates CV and VLM analysis of drawings.
"""

import logging
from typing import Any, Optional

import numpy as np

from backend.shared.config import get_settings
from backend.shared.models import (
    Job,
    JobStatus,
    SceneGraph,
    View,
    ViewType,
    Component,
    Annotation,
    BoundingBox,
)
from backend.shared.s3_client import S3Client, get_s3_client
from backend.vlm_client import BedrockClaudeVLM, VLMClient
from backend.vision.cv_detector import CVDetector
from backend.vision.region_segmenter import RegionSegmenter
from backend.vision.component_classifier import ComponentClassifier

logger = logging.getLogger(__name__)


class VisionHandler:
    """
    Main vision analysis handler.
    
    Combines:
    - Classical CV for line/edge detection
    - VLM for semantic understanding
    - Region segmentation
    - Component classification
    """
    
    def __init__(
        self,
        s3_client: Optional[S3Client] = None,
        vlm_client: Optional[VLMClient] = None,
        settings: Optional[Any] = None,
    ):
        """
        Initialize vision handler.
        
        Args:
            s3_client: Optional S3 client
            vlm_client: Optional VLM client
            settings: Optional settings
        """
        self.s3_client = s3_client or get_s3_client()
        self.vlm_client = vlm_client or BedrockClaudeVLM()
        self.settings = settings or get_settings()
        
        self.cv_detector = CVDetector()
        self.region_segmenter = RegionSegmenter(self.vlm_client)
        self.component_classifier = ComponentClassifier(self.vlm_client)
    
    async def analyze(
        self,
        job: Job,
        image: Optional[np.ndarray] = None,
    ) -> tuple[Job, SceneGraph]:
        """
        Perform full vision analysis on a drawing.
        
        Args:
            job: Job to process
            image: Optional image array (will fetch from S3 if not provided)
            
        Returns:
            Tuple of (updated job, scene graph)
        """
        logger.info(f"Starting vision analysis for job {job.id}")
        
        job.update_status(JobStatus.ANALYZING, "vision_analysis", 25)
        
        try:
            # Load image if not provided
            if image is None:
                if job.output.normalized_image:
                    image = self._load_image_from_s3(job.output.normalized_image.key)
                else:
                    raise ValueError("No normalized image available")
            
            # Initialize scene graph
            scene_graph = SceneGraph(
                job_id=job.id,
                image_width=image.shape[1],
                image_height=image.shape[0],
            )
            
            # Step 1: Get high-level drawing description
            logger.info("Getting drawing description from VLM")
            description = await self._get_drawing_description(image)
            scene_graph.title = description.get("title", "Unknown Drawing")
            scene_graph.add_processing_note(f"Drawing type: {description.get('drawing_type', 'unknown')}")
            
            job.update_status(JobStatus.ANALYZING, "region_segmentation", 35)
            
            # Step 2: Segment regions using VLM
            logger.info("Segmenting regions")
            regions = await self.region_segmenter.segment(image)
            
            # Convert regions to views
            for region in regions:
                view = View(
                    name=region.label,
                    view_type=self._map_view_type(region.attributes.get("type", "unknown")),
                    bounds=BoundingBox(
                        x=region.x * image.shape[1],
                        y=region.y * image.shape[0],
                        width=region.width * image.shape[1],
                        height=region.height * image.shape[0],
                    ),
                    classification_confidence=region.confidence,
                )
                scene_graph.views.append(view)
            
            job.update_status(JobStatus.ANALYZING, "cv_detection", 45)
            
            # Step 3: Run CV detection
            logger.info("Running CV detection")
            cv_results = self.cv_detector.detect(image)
            
            # Add detected lines/edges to scene graph
            scene_graph.add_processing_note(
                f"CV detected {len(cv_results.get('lines', []))} lines, "
                f"{len(cv_results.get('contours', []))} contours"
            )
            
            job.update_status(JobStatus.ANALYZING, "component_classification", 55)
            
            # Step 4: Identify components in each region
            logger.info("Classifying components")
            for view in scene_graph.views:
                # Crop region
                region_image = self._crop_region(image, view.bounds)
                
                # Classify components in this region
                components = await self.component_classifier.classify_region(
                    region_image,
                    view.view_type.value,
                )
                
                for comp in components:
                    component = Component(
                        name=comp.suggested_name,
                        component_type=self._map_component_type(comp.component_type),
                        view_id=view.id,
                        bounds=BoundingBox(
                            x=view.bounds.x + comp.bounds.x if hasattr(comp, 'bounds') else view.bounds.x,
                            y=view.bounds.y + comp.bounds.y if hasattr(comp, 'bounds') else view.bounds.y,
                            width=comp.bounds.width if hasattr(comp, 'bounds') else view.bounds.width * 0.1,
                            height=comp.bounds.height if hasattr(comp, 'bounds') else view.bounds.height * 0.1,
                        ) if hasattr(comp, 'bounds') else view.bounds,
                        classification_confidence=comp.confidence,
                    )
                    
                    if comp.material:
                        from backend.shared.models import MaterialType
                        try:
                            component.attributes.material = MaterialType(comp.material.lower())
                        except ValueError:
                            pass
                    
                    scene_graph.components.append(component)
                    view.component_ids.append(component.id)
            
            job.update_status(JobStatus.ANALYZING, "analysis_complete", 60)
            
            logger.info(
                f"Vision analysis complete: {len(scene_graph.views)} views, "
                f"{len(scene_graph.components)} components"
            )
            
            return job, scene_graph
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            job.set_error(f"Vision analysis failed: {str(e)}")
            raise
    
    async def _get_drawing_description(self, image: np.ndarray) -> dict:
        """Get high-level drawing description from VLM."""
        from PIL import Image
        import io
        
        # Convert to bytes for VLM
        pil_image = Image.fromarray(image)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        
        response = await self.vlm_client.describe_drawing(image_bytes)
        
        if response.success and response.structured_data:
            return response.structured_data
        
        return {"title": "Unknown", "drawing_type": "unknown"}
    
    def _load_image_from_s3(self, key: str) -> np.ndarray:
        """Load image from S3."""
        from PIL import Image
        import io
        
        data = self.s3_client.download_bytes(key)
        image = Image.open(io.BytesIO(data))
        return np.array(image)
    
    def _crop_region(self, image: np.ndarray, bounds: BoundingBox) -> np.ndarray:
        """Crop a region from the image."""
        x1 = int(max(0, bounds.x))
        y1 = int(max(0, bounds.y))
        x2 = int(min(image.shape[1], bounds.x + bounds.width))
        y2 = int(min(image.shape[0], bounds.y + bounds.height))
        
        return image[y1:y2, x1:x2]
    
    def _map_view_type(self, type_str: str) -> ViewType:
        """Map string to ViewType enum."""
        mapping = {
            "top_view": ViewType.TOP,
            "top": ViewType.TOP,
            "side_view": ViewType.SIDE,
            "side": ViewType.SIDE,
            "front_view": ViewType.FRONT,
            "front": ViewType.FRONT,
            "rear_view": ViewType.REAR,
            "rear": ViewType.REAR,
            "section": ViewType.SECTION,
            "section_view": ViewType.SECTION,
            "detail": ViewType.DETAIL,
            "detail_view": ViewType.DETAIL,
            "isometric": ViewType.ISOMETRIC,
        }
        return mapping.get(type_str.lower(), ViewType.UNKNOWN)
    
    def _map_component_type(self, type_str: str) -> "ComponentType":
        """Map string to ComponentType enum."""
        from backend.shared.models import ComponentType
        
        mapping = {
            "rib": ComponentType.RIB,
            "former": ComponentType.FORMER,
            "bulkhead": ComponentType.BULKHEAD,
            "spar": ComponentType.SPAR,
            "stringer": ComponentType.STRINGER,
            "longeron": ComponentType.LONGERON,
            "skin": ComponentType.SKIN,
            "covering": ComponentType.COVERING,
            "aileron": ComponentType.AILERON,
            "elevator": ComponentType.ELEVATOR,
            "rudder": ComponentType.RUDDER,
            "flap": ComponentType.FLAP,
            "fastener": ComponentType.FASTENER,
            "hinge": ComponentType.HINGE,
            "bracket": ComponentType.BRACKET,
            "mount": ComponentType.MOUNT,
            "motor": ComponentType.MOTOR,
            "propeller": ComponentType.PROPELLER,
            "engine": ComponentType.ENGINE,
            "wheel": ComponentType.WHEEL,
            "strut": ComponentType.STRUT,
            "skid": ComponentType.SKID,
        }
        return mapping.get(type_str.lower(), ComponentType.UNKNOWN)


# Lambda handler entry point
def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for vision function."""
    import asyncio
    from backend.shared.dynamo_client import get_dynamo_client
    
    job_id = event.get("job_id")
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}
    
    dynamo = get_dynamo_client()
    job = dynamo.get_job(job_id)
    
    if not job:
        return {"status": "error", "message": f"Job not found: {job_id}"}
    
    handler = VisionHandler()
    
    try:
        job, scene_graph = asyncio.run(handler.analyze(job))
        
        dynamo.update_job(job)
        dynamo.create_scene_graph(scene_graph)
        
        job.scene_graph_id = scene_graph.id
        dynamo.update_job(job)
        
        return {
            "status": "success",
            "job_id": job.id,
            "scene_graph_id": scene_graph.id,
            "views_count": len(scene_graph.views),
            "components_count": len(scene_graph.components),
        }
        
    except Exception as e:
        job.set_error(str(e))
        dynamo.update_job(job)
        
        return {
            "status": "error",
            "job_id": job.id,
            "message": str(e),
        }


