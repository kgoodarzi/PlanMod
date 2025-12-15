"""Schema definitions for VLM API requests and responses."""

from typing import List, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box in image coordinates."""
    x_min: float = Field(..., description="Minimum X coordinate (0-1 normalized)")
    y_min: float = Field(..., description="Minimum Y coordinate (0-1 normalized)")
    x_max: float = Field(..., description="Maximum X coordinate (0-1 normalized)")
    y_max: float = Field(..., description="Maximum Y coordinate (0-1 normalized)")


class ComponentAnnotation(BaseModel):
    """Annotation for a detected component."""
    label: str = Field(..., description="Component type (spar, rib, longeron, etc.)")
    bbox: BoundingBox = Field(..., description="Bounding box in image coordinates")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    dimensions: Optional[str] = Field(None, description="Extracted dimensions if readable")
    notes: Optional[str] = Field(None, description="Additional notes from VLM")


class ViewAnnotation(BaseModel):
    """Annotation for a detected view (front, top, side)."""
    view_type: str = Field(..., description="View type: front, top, or side")
    bbox: BoundingBox = Field(..., description="Bounding box of view region")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")


class VLMResponse(BaseModel):
    """Structured response from VLM analysis."""
    views: List[ViewAnnotation] = Field(default_factory=list, description="Detected views")
    components: List[ComponentAnnotation] = Field(
        default_factory=list, description="Detected components"
    )
    text_annotations: List[str] = Field(
        default_factory=list, description="Extracted text labels"
    )
    raw_response: Optional[str] = Field(None, description="Raw VLM response text")

