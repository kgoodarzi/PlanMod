"""
Main handler for vectorization module.
"""

import logging
from typing import Any, Optional

import numpy as np

from backend.shared.config import get_settings
from backend.shared.models import (
    Job,
    JobStatus,
    SceneGraph,
    GeometryEntity,
    Point2D,
    Line2D,
    Polyline2D,
)
from backend.vectorization.line_detector import LineDetector
from backend.vectorization.contour_tracer import ContourTracer
from backend.vectorization.arc_fitter import ArcFitter

logger = logging.getLogger(__name__)


class VectorizationHandler:
    """
    Main vectorization handler.
    
    Converts raster drawings to vector geometry:
    - Lines
    - Polylines
    - Arcs and circles
    """
    
    def __init__(self, settings: Optional[Any] = None):
        """Initialize vectorization handler."""
        self.settings = settings or get_settings()
        
        self.line_detector = LineDetector()
        self.contour_tracer = ContourTracer()
        self.arc_fitter = ArcFitter()
    
    def vectorize(
        self,
        image: np.ndarray,
        scene_graph: SceneGraph,
    ) -> SceneGraph:
        """
        Vectorize image and update scene graph with geometry entities.
        
        Args:
            image: Input image
            scene_graph: Scene graph to update
            
        Returns:
            Updated scene graph with geometry entities
        """
        logger.info("Vectorizing image")
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            import cv2
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Detect lines
        lines = self.line_detector.detect(gray)
        logger.info(f"Detected {len(lines)} lines")
        
        # Trace contours
        contours = self.contour_tracer.trace(gray)
        logger.info(f"Traced {len(contours)} contours")
        
        # Fit arcs
        arcs = self.arc_fitter.fit_contours(contours)
        logger.info(f"Fitted {len(arcs)} arcs")
        
        # Add entities to scene graph
        for i, line in enumerate(lines):
            entity = GeometryEntity(
                entity_type="line",
                geometry={
                    "start": {"x": line["start"][0], "y": line["start"][1]},
                    "end": {"x": line["end"][0], "y": line["end"][1]},
                    "length": line.get("length", 0),
                    "angle": line.get("angle", 0),
                },
            )
            
            # Associate with view if possible
            entity.view_id = self._find_containing_view(
                scene_graph,
                (line["start"][0] + line["end"][0]) / 2,
                (line["start"][1] + line["end"][1]) / 2,
            )
            
            scene_graph.entities.append(entity)
        
        for i, contour in enumerate(contours):
            if contour["is_closed"] and len(contour["points"]) > 4:
                entity = GeometryEntity(
                    entity_type="polyline",
                    geometry={
                        "points": contour["points"],
                        "closed": contour["is_closed"],
                        "area": contour.get("area", 0),
                    },
                )
                scene_graph.entities.append(entity)
        
        for i, arc in enumerate(arcs):
            entity = GeometryEntity(
                entity_type="arc" if arc["type"] == "arc" else "circle",
                geometry=arc,
            )
            scene_graph.entities.append(entity)
        
        scene_graph.add_processing_note(
            f"Vectorization: {len(lines)} lines, {len(contours)} contours, {len(arcs)} arcs"
        )
        
        return scene_graph
    
    def _find_containing_view(
        self,
        scene_graph: SceneGraph,
        x: float,
        y: float,
    ) -> Optional[str]:
        """Find the view that contains a point."""
        for view in scene_graph.views:
            if view.bounds.contains(x, y):
                return view.id
        return None


# Lambda handler
def lambda_handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point."""
    from backend.shared.dynamo_client import get_dynamo_client
    from backend.shared.s3_client import get_s3_client
    from PIL import Image
    import io
    
    job_id = event.get("job_id")
    if not job_id:
        return {"status": "error", "message": "Missing job_id"}
    
    dynamo = get_dynamo_client()
    s3 = get_s3_client()
    
    job = dynamo.get_job(job_id)
    if not job:
        return {"status": "error", "message": f"Job not found: {job_id}"}
    
    scene_graph = dynamo.get_scene_graph_by_job(job_id)
    if not scene_graph:
        return {"status": "error", "message": "Scene graph not found"}
    
    try:
        # Load image
        image_data = s3.download_bytes(job.output.normalized_image.key)
        image = np.array(Image.open(io.BytesIO(image_data)))
        
        # Vectorize
        handler = VectorizationHandler()
        scene_graph = handler.vectorize(image, scene_graph)
        
        # Save
        dynamo.update_scene_graph(scene_graph)
        job.update_status(JobStatus.VECTORIZING, "vectorization_complete", 70)
        dynamo.update_job(job)
        
        return {
            "status": "success",
            "job_id": job_id,
            "entities_count": len(scene_graph.entities),
        }
        
    except Exception as e:
        job.set_error(str(e))
        dynamo.update_job(job)
        return {"status": "error", "message": str(e)}


