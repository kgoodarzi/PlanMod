"""
Core data models for PlanMod.

These models define the structure of jobs, scene graphs, components,
and other entities used throughout the pipeline.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enumerations
# =============================================================================

class JobStatus(str, Enum):
    """Status of a processing job."""
    
    PENDING = "pending"
    UPLOADING = "uploading"
    INGESTING = "ingesting"
    ANALYZING = "analyzing"
    VECTORIZING = "vectorizing"
    BUILDING_GRAPH = "building_graph"
    GENERATING_DXF = "generating_dxf"
    TRANSFORMING = "transforming"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ViewType(str, Enum):
    """Type of view in a technical drawing."""
    
    TOP = "top"
    SIDE = "side"
    FRONT = "front"
    REAR = "rear"
    SECTION = "section"
    DETAIL = "detail"
    ISOMETRIC = "isometric"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Type of component identified in a drawing."""
    
    # Structural
    RIB = "rib"
    FORMER = "former"
    BULKHEAD = "bulkhead"
    SPAR = "spar"
    STRINGER = "stringer"
    LONGERON = "longeron"
    
    # Surfaces
    SKIN = "skin"
    COVERING = "covering"
    
    # Control surfaces
    AILERON = "aileron"
    ELEVATOR = "elevator"
    RUDDER = "rudder"
    FLAP = "flap"
    
    # Hardware
    FASTENER = "fastener"
    HINGE = "hinge"
    BRACKET = "bracket"
    MOUNT = "mount"
    
    # Propulsion
    MOTOR = "motor"
    PROPELLER = "propeller"
    ENGINE = "engine"
    
    # Landing gear
    WHEEL = "wheel"
    STRUT = "strut"
    SKID = "skid"
    
    # Materials
    BALSA_SHEET = "balsa_sheet"
    BALSA_STICK = "balsa_stick"
    PLYWOOD = "plywood"
    CARBON_FIBER = "carbon_fiber"
    
    # Generic
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class MaterialType(str, Enum):
    """Type of material for components."""
    
    BALSA = "balsa"
    PLYWOOD = "plywood"
    HARDWOOD = "hardwood"
    CARBON_FIBER = "carbon_fiber"
    FIBERGLASS = "fiberglass"
    FOAM = "foam"
    ALUMINUM = "aluminum"
    STEEL = "steel"
    PLASTIC = "plastic"
    UNKNOWN = "unknown"


# =============================================================================
# Base Models
# =============================================================================

class S3Reference(BaseModel):
    """Reference to a file stored in S3."""
    
    bucket: str
    key: str
    version_id: Optional[str] = None
    
    @property
    def uri(self) -> str:
        """Get S3 URI for this reference."""
        return f"s3://{self.bucket}/{self.key}"
    
    @classmethod
    def from_uri(cls, uri: str) -> "S3Reference":
        """Create from S3 URI string."""
        # Remove s3:// prefix
        path = uri.replace("s3://", "")
        parts = path.split("/", 1)
        return cls(bucket=parts[0], key=parts[1] if len(parts) > 1 else "")


class BoundingBox(BaseModel):
    """2D bounding box for regions and components."""
    
    x: float = Field(description="X coordinate of top-left corner")
    y: float = Field(description="Y coordinate of top-left corner")
    width: float = Field(description="Width of bounding box")
    height: float = Field(description="Height of bounding box")
    
    @property
    def x2(self) -> float:
        """Right edge X coordinate."""
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        """Bottom edge Y coordinate."""
        return self.y + self.height
    
    @property
    def center(self) -> tuple[float, float]:
        """Center point of bounding box."""
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def area(self) -> float:
        """Area of bounding box."""
        return self.width * self.height
    
    def contains(self, x: float, y: float) -> bool:
        """Check if point is inside bounding box."""
        return self.x <= x <= self.x2 and self.y <= y <= self.y2
    
    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if this box overlaps with another."""
        return not (
            self.x2 < other.x or
            self.x > other.x2 or
            self.y2 < other.y or
            self.y > other.y2
        )
    
    def intersection(self, other: "BoundingBox") -> Optional["BoundingBox"]:
        """Get intersection with another bounding box."""
        if not self.overlaps(other):
            return None
        
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        x2 = min(self.x2, other.x2)
        y2 = min(self.y2, other.y2)
        
        return BoundingBox(x=x, y=y, width=x2 - x, height=y2 - y)


class Point2D(BaseModel):
    """2D point."""
    
    x: float
    y: float
    
    def distance_to(self, other: "Point2D") -> float:
        """Calculate distance to another point."""
        import math
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


class Line2D(BaseModel):
    """2D line segment."""
    
    start: Point2D
    end: Point2D
    
    @property
    def length(self) -> float:
        """Length of line segment."""
        return self.start.distance_to(self.end)
    
    @property
    def midpoint(self) -> Point2D:
        """Midpoint of line segment."""
        return Point2D(
            x=(self.start.x + self.end.x) / 2,
            y=(self.start.y + self.end.y) / 2
        )


class Arc2D(BaseModel):
    """2D arc."""
    
    center: Point2D
    radius: float
    start_angle: float  # In degrees
    end_angle: float  # In degrees


class Polyline2D(BaseModel):
    """2D polyline (sequence of connected points)."""
    
    points: list[Point2D]
    closed: bool = False
    
    @property
    def num_segments(self) -> int:
        """Number of line segments."""
        if len(self.points) < 2:
            return 0
        return len(self.points) - 1 + (1 if self.closed else 0)


# =============================================================================
# Annotation Models
# =============================================================================

class Annotation(BaseModel):
    """Text annotation from OCR or manual labeling."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    bounds: BoundingBox
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    annotation_type: str = "text"  # text, dimension, label, note
    associated_component_id: Optional[str] = None
    
    # Parsed dimension info (if applicable)
    dimension_value: Optional[float] = None
    dimension_unit: Optional[str] = None


class Dimension(BaseModel):
    """Parsed dimension with value and unit."""
    
    value: float
    unit: str = "mm"  # mm, in, cm
    text: str  # Original text
    
    def to_mm(self) -> float:
        """Convert to millimeters."""
        conversions = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
        return self.value * conversions.get(self.unit, 1.0)
    
    def to_inches(self) -> float:
        """Convert to inches."""
        return self.to_mm() / 25.4


# =============================================================================
# Component Models
# =============================================================================

class ComponentAttributes(BaseModel):
    """Attributes for a component."""
    
    material: Optional[MaterialType] = None
    thickness: Optional[Dimension] = None
    width: Optional[Dimension] = None
    length: Optional[Dimension] = None
    
    # Material properties
    density_kg_m3: Optional[float] = None
    
    # Custom attributes
    custom: dict[str, Any] = Field(default_factory=dict)


class Component(BaseModel):
    """
    A component identified in the drawing.
    
    Components are the semantic units that can be substituted
    or modified in the transformation phase.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    component_type: ComponentType = ComponentType.UNKNOWN
    view_id: Optional[str] = None
    
    # Geometry
    bounds: BoundingBox
    geometry_refs: list[str] = Field(default_factory=list)  # References to vector entities
    
    # Attributes
    attributes: ComponentAttributes = Field(default_factory=ComponentAttributes)
    
    # Annotations associated with this component
    annotation_ids: list[str] = Field(default_factory=list)
    
    # Confidence scores
    classification_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # DXF mapping
    dxf_layer: Optional[str] = None
    dxf_block_name: Optional[str] = None
    
    # Catalog reference
    catalog_id: Optional[str] = None
    
    def get_layer_name(self) -> str:
        """Generate DXF layer name for this component."""
        type_prefix = self.component_type.value.upper()
        return f"COMP_{type_prefix}_{self.id[:8]}"


# =============================================================================
# View Models
# =============================================================================

class View(BaseModel):
    """
    A view region in the drawing (top, side, front, etc.).
    
    Views contain components and geometry entities.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    view_type: ViewType = ViewType.UNKNOWN
    bounds: BoundingBox
    
    # Components in this view
    component_ids: list[str] = Field(default_factory=list)
    
    # Geometry entity IDs
    entity_ids: list[str] = Field(default_factory=list)
    
    # View metadata
    scale: Optional[float] = None
    title: Optional[str] = None
    
    # Confidence score for view classification
    classification_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    def get_layer_name(self) -> str:
        """Generate DXF layer name for this view."""
        return f"VIEW_{self.view_type.value.upper()}"


# =============================================================================
# Scene Graph
# =============================================================================

class GeometryEntity(BaseModel):
    """A vector geometry entity (line, arc, polyline)."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str  # line, arc, polyline, circle, ellipse
    
    # Geometry data (type-specific)
    geometry: dict[str, Any] = Field(default_factory=dict)
    
    # Association
    view_id: Optional[str] = None
    component_id: Optional[str] = None
    
    # DXF properties
    layer: Optional[str] = None
    color: Optional[int] = None
    linetype: Optional[str] = None


class Relationship(BaseModel):
    """Relationship between entities in the scene graph."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    relationship_type: str  # contains, adjacent_to, connected_to, part_of
    source_id: str
    target_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneGraph(BaseModel):
    """
    The semantic model of the entire drawing.
    
    This is the source of truth for all recognized elements
    and their relationships.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    
    # Drawing metadata
    title: Optional[str] = None
    source_file: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Image dimensions
    image_width: int = 0
    image_height: int = 0
    
    # Views
    views: list[View] = Field(default_factory=list)
    
    # Components (across all views)
    components: list[Component] = Field(default_factory=list)
    
    # Annotations (text, dimensions, labels)
    annotations: list[Annotation] = Field(default_factory=list)
    
    # Geometry entities
    entities: list[GeometryEntity] = Field(default_factory=list)
    
    # Relationships
    relationships: list[Relationship] = Field(default_factory=list)
    
    # Processing metadata
    processing_notes: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    
    def get_view(self, view_id: str) -> Optional[View]:
        """Get view by ID."""
        for view in self.views:
            if view.id == view_id:
                return view
        return None
    
    def get_component(self, component_id: str) -> Optional[Component]:
        """Get component by ID."""
        for component in self.components:
            if component.id == component_id:
                return component
        return None
    
    def get_components_by_type(self, component_type: ComponentType) -> list[Component]:
        """Get all components of a specific type."""
        return [c for c in self.components if c.component_type == component_type]
    
    def get_components_in_view(self, view_id: str) -> list[Component]:
        """Get all components in a specific view."""
        return [c for c in self.components if c.view_id == view_id]
    
    def add_processing_note(self, note: str) -> None:
        """Add a processing note."""
        self.processing_notes.append(note)
        self.updated_at = datetime.utcnow()
    
    def add_uncertainty(self, uncertainty: str) -> None:
        """Add an uncertainty that needs human review."""
        self.uncertainties.append(uncertainty)
        self.updated_at = datetime.utcnow()


# =============================================================================
# Job Models
# =============================================================================

class JobInput(BaseModel):
    """Input specification for a processing job."""
    
    file_name: str
    file_type: str  # pdf, png, jpg, dxf, dwg
    file_size: int
    s3_reference: Optional[S3Reference] = None


class JobOutput(BaseModel):
    """Output files from a processing job."""
    
    normalized_image: Optional[S3Reference] = None
    base_dxf: Optional[S3Reference] = None
    final_dxf: Optional[S3Reference] = None
    scene_graph_json: Optional[S3Reference] = None
    scene_graph_image: Optional[S3Reference] = None
    report: Optional[S3Reference] = None


class SubstitutionRule(BaseModel):
    """Rule for component substitution in transform phase."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Target specification
    target_component_id: Optional[str] = None  # Specific component
    target_component_type: Optional[ComponentType] = None  # All of type
    target_criteria: dict[str, Any] = Field(default_factory=dict)  # Custom criteria
    
    # Replacement specification
    replacement_catalog_id: Optional[str] = None
    replacement_attributes: dict[str, Any] = Field(default_factory=dict)
    
    # Description
    description: str = ""


class Job(BaseModel):
    """
    A processing job representing end-to-end pipeline execution.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Status tracking
    status: JobStatus = JobStatus.PENDING
    current_stage: str = "created"
    progress_percent: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Input/Output
    input: Optional[JobInput] = None
    output: JobOutput = Field(default_factory=JobOutput)
    
    # Scene graph reference
    scene_graph_id: Optional[str] = None
    
    # Substitution rules for transform phase
    substitution_rules: list[SubstitutionRule] = Field(default_factory=list)
    
    # Results
    mass_kg: Optional[float] = None
    center_of_gravity: Optional[Point2D] = None
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[dict[str, Any]] = None
    
    # Processing metadata
    processing_time_seconds: Optional[float] = None
    
    def update_status(self, status: JobStatus, stage: str, progress: int = 0) -> None:
        """Update job status."""
        self.status = status
        self.current_stage = stage
        self.progress_percent = progress
        self.updated_at = datetime.utcnow()
        
        if status == JobStatus.PENDING and self.started_at is None:
            self.started_at = datetime.utcnow()
        elif status in (JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED):
            self.completed_at = datetime.utcnow()
            if self.started_at:
                self.processing_time_seconds = (
                    self.completed_at - self.started_at
                ).total_seconds()
    
    def set_error(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        """Set error state."""
        self.status = JobStatus.FAILED
        self.error_message = message
        self.error_details = details
        self.updated_at = datetime.utcnow()
        self.completed_at = datetime.utcnow()


# =============================================================================
# API Models
# =============================================================================

class CreateJobRequest(BaseModel):
    """Request to create a new processing job."""
    
    file_name: str
    file_type: str


class CreateJobResponse(BaseModel):
    """Response after creating a job."""
    
    job_id: str
    upload_url: str  # Pre-signed S3 URL for upload
    status: JobStatus


class JobStatusResponse(BaseModel):
    """Response with job status."""
    
    job_id: str
    status: JobStatus
    current_stage: str
    progress_percent: int
    error_message: Optional[str] = None


class SubstitutionRequest(BaseModel):
    """Request to apply substitutions."""
    
    job_id: str
    rules: list[SubstitutionRule]


class SubstitutionResponse(BaseModel):
    """Response after applying substitutions."""
    
    job_id: str
    status: JobStatus
    final_dxf_url: Optional[str] = None
    mass_kg: Optional[float] = None
    center_of_gravity: Optional[tuple[float, float]] = None


