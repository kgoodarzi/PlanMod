"""3D scene graph representation of aircraft structure."""

from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    """Types of aircraft components."""
    SPAR = "spar"
    RIB = "rib"
    FORMER = "former"
    LONGERON = "longeron"
    STRINGER = "stringer"
    STICK = "stick"
    PLATE = "plate"
    SHEETING = "sheeting"
    HARDWARE = "hardware"
    LEADING_EDGE = "leading_edge"
    TRAILING_EDGE = "trailing_edge"
    UNKNOWN = "unknown"


class Vector3D(BaseModel):
    """3D vector/point."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class BoundingBox3D(BaseModel):
    """3D bounding box."""
    min: Vector3D
    max: Vector3D


class Component(BaseModel):
    """A single component in the scene graph."""
    id: str = Field(..., description="Unique component identifier")
    type: ComponentType = Field(..., description="Component type")
    position: Vector3D = Field(default_factory=lambda: Vector3D(), description="3D position")
    orientation: Vector3D = Field(
        default_factory=lambda: Vector3D(), description="Rotation angles (degrees)"
    )
    dimensions: Dict[str, float] = Field(
        default_factory=dict, description="Component dimensions (width, height, length, etc.)"
    )
    material: str = Field(default="balsa", description="Material type")
    material_properties: Dict[str, float] = Field(
        default_factory=dict, description="Density, strength, etc."
    )
    dxf_entity_ids: List[str] = Field(
        default_factory=list, description="Associated DXF entity IDs"
    )
    view_annotations: Dict[str, Dict] = Field(
        default_factory=dict, description="VLM annotations per view"
    )
    parent_id: Optional[str] = Field(None, description="Parent component ID")
    children_ids: List[str] = Field(
        default_factory=list, description="Child component IDs"
    )


class SceneGraph(BaseModel):
    """3D scene graph representing the aircraft structure."""
    components: Dict[str, Component] = Field(
        default_factory=dict, description="All components indexed by ID"
    )
    metadata: Dict = Field(
        default_factory=dict, description="Scene metadata (bounds, units, etc.)"
    )

    def get_component(self, component_id: str) -> Optional[Component]:
        """Get component by ID."""
        return self.components.get(component_id)

    def add_component(self, component: Component):
        """Add a component to the scene graph."""
        self.components[component.id] = component

    def remove_component(self, component_id: str):
        """Remove a component from the scene graph."""
        if component_id in self.components:
            component = self.components[component_id]
            # Remove from parent's children
            if component.parent_id:
                parent = self.components.get(component.parent_id)
                if parent and component_id in parent.children_ids:
                    parent.children_ids.remove(component_id)
            # Remove children
            for child_id in component.children_ids:
                if child_id in self.components:
                    self.components[child_id].parent_id = None
            del self.components[component_id]

    def get_components_by_type(self, component_type: ComponentType) -> List[Component]:
        """Get all components of a specific type."""
        return [c for c in self.components.values() if c.type == component_type]


class SceneGraphBuilder:
    """Build scene graph from DXF entities and VLM annotations."""

    def __init__(self, dxf_parser, vlm_responses: Dict):
        """
        Initialize builder.
        
        Args:
            dxf_parser: DXFParser instance
            vlm_responses: Dictionary mapping view names to VLMResponse objects
        """
        self.dxf_parser = dxf_parser
        self.vlm_responses = vlm_responses
        self.dxf_bounds = dxf_parser.get_bounds()

    def build(self) -> SceneGraph:
        """Build scene graph from DXF and VLM data."""
        scene = SceneGraph()
        scene.metadata = {
            "dxf_bounds": self.dxf_bounds,
            "units": "inches",  # Typical for balsa models
        }
        
        # Extract components from VLM annotations
        component_counter = 0
        
        for view_name, vlm_response in self.vlm_responses.items():
            for comp_ann in vlm_response.components:
                component_id = f"{comp_ann.label}_{component_counter}"
                component_counter += 1
                
                # Map image bbox to DXF coordinates
                dxf_bbox = self._image_to_dxf_coords(comp_ann.bbox)
                
                # Infer 3D position (simplified for MVP)
                position = self._infer_3d_position(comp_ann, view_name)
                
                # Determine component type
                comp_type = self._classify_component_type(comp_ann.label)
                
                # Find associated DXF entities
                dxf_entities = self._find_dxf_entities_in_bbox(dxf_bbox)
                entity_ids = [str(id(e)) for e in dxf_entities]
                
                component = Component(
                    id=component_id,
                    type=comp_type,
                    position=position,
                    dimensions=self._extract_dimensions(comp_ann),
                    view_annotations={view_name: comp_ann.dict()},
                    dxf_entity_ids=entity_ids,
                )
                
                scene.add_component(component)
        
        # Infer relationships (parent-child)
        self._infer_relationships(scene)
        
        return scene

    def _image_to_dxf_coords(self, bbox) -> Tuple[float, float, float, float]:
        """Convert normalized image bbox to DXF coordinates."""
        min_x, min_y, max_x, max_y = self.dxf_bounds
        width = max_x - min_x
        height = max_y - min_y
        
        dxf_x_min = min_x + bbox.x_min * width
        dxf_y_min = min_y + bbox.y_min * height
        dxf_x_max = min_x + bbox.x_max * width
        dxf_y_max = min_y + bbox.y_max * height
        
        return (dxf_x_min, dxf_y_min, dxf_x_max, dxf_y_max)

    def _infer_3d_position(self, comp_ann, view_name: str) -> Vector3D:
        """
        Infer 3D position from 2D view annotation.
        
        Simplified MVP: assumes views are arranged in standard orthographic layout.
        """
        # For MVP, use simplified heuristics
        # In production, would use multi-view geometry reconstruction
        
        bbox_center_x = (comp_ann.bbox.x_min + comp_ann.bbox.x_max) / 2
        bbox_center_y = (comp_ann.bbox.y_min + comp_ann.bbox.y_max) / 2
        
        if "front" in view_name.lower():
            # Front view: X and Y known, Z inferred from position
            return Vector3D(
                x=bbox_center_x,
                y=bbox_center_y,
                z=0.0,  # Simplified
            )
        elif "top" in view_name.lower():
            # Top view: X and Z known, Y inferred
            return Vector3D(
                x=bbox_center_x,
                y=0.0,  # Simplified
                z=bbox_center_y,
            )
        elif "side" in view_name.lower():
            # Side view: Y and Z known, X inferred
            return Vector3D(
                x=0.0,  # Simplified
                y=bbox_center_x,
                z=bbox_center_y,
            )
        else:
            # Default: use image center
            return Vector3D(x=bbox_center_x, y=bbox_center_y, z=0.0)

    def _classify_component_type(self, label: str) -> ComponentType:
        """Classify component type from VLM label."""
        label_lower = label.lower()
        
        if "spar" in label_lower:
            return ComponentType.SPAR
        elif "rib" in label_lower:
            return ComponentType.RIB
        elif "former" in label_lower:
            return ComponentType.FORMER
        elif "longeron" in label_lower:
            return ComponentType.LONGERON
        elif "stringer" in label_lower:
            return ComponentType.STRINGER
        elif "stick" in label_lower or "strip" in label_lower:
            return ComponentType.STICK
        elif "plate" in label_lower:
            return ComponentType.PLATE
        elif "sheet" in label_lower:
            return ComponentType.SHEETING
        elif "hardware" in label_lower or "hinge" in label_lower:
            return ComponentType.HARDWARE
        elif "leading" in label_lower:
            return ComponentType.LEADING_EDGE
        elif "trailing" in label_lower:
            return ComponentType.TRAILING_EDGE
        else:
            return ComponentType.UNKNOWN

    def _find_dxf_entities_in_bbox(
        self, bbox: Tuple[float, float, float, float]
    ) -> List:
        """Find DXF entities within bounding box."""
        x_min, y_min, x_max, y_max = bbox
        entities = []
        
        for entity in self.dxf_parser.get_entities():
            # Simple bbox check
            if hasattr(entity, "bbox"):
                entity_bbox = entity.bbox()
                if entity_bbox:
                    if (
                        entity_bbox.extmin.x >= x_min
                        and entity_bbox.extmin.y >= y_min
                        and entity_bbox.extmax.x <= x_max
                        and entity_bbox.extmax.y <= y_max
                    ):
                        entities.append(entity)
        
        return entities

    def _extract_dimensions(self, comp_ann) -> Dict[str, float]:
        """Extract dimensions from component annotation."""
        dims = {}
        
        if comp_ann.dimensions:
            # Try to parse dimensions string (e.g., "1/8\" x 1/4\"")
            import re
            matches = re.findall(r"(\d+/\d+|\d+\.\d+|\d+)", comp_ann.dimensions)
            if len(matches) >= 2:
                try:
                    dims["width"] = self._parse_fraction(matches[0])
                    dims["height"] = self._parse_fraction(matches[1])
                except:
                    pass
        
        return dims

    def _parse_fraction(self, frac_str: str) -> float:
        """Parse fraction string to float."""
        if "/" in frac_str:
            num, den = frac_str.split("/")
            return float(num) / float(den)
        else:
            return float(frac_str)

    def _infer_relationships(self, scene: SceneGraph):
        """Infer parent-child relationships between components."""
        # Simplified MVP: components that intersect are related
        # In production, would use more sophisticated geometric analysis
        
        components = list(scene.components.values())
        
        for i, comp1 in enumerate(components):
            for comp2 in components[i + 1 :]:
                if self._components_intersect(comp1, comp2):
                    # Make comp2 a child of comp1 if comp1 is larger
                    if self._component_size(comp1) > self._component_size(comp2):
                        comp2.parent_id = comp1.id
                        comp1.children_ids.append(comp2.id)

    def _components_intersect(self, comp1: Component, comp2: Component) -> bool:
        """Check if two components intersect (simplified)."""
        # Simplified: check if positions are close
        dist = (
            (comp1.position.x - comp2.position.x) ** 2
            + (comp1.position.y - comp2.position.y) ** 2
            + (comp1.position.z - comp2.position.z) ** 2
        ) ** 0.5
        return dist < 1.0  # Threshold in inches

    def _component_size(self, comp: Component) -> float:
        """Get approximate component size."""
        dims = comp.dimensions
        if "width" in dims and "height" in dims:
            return dims.get("width", 0) * dims.get("height", 0)
        return 1.0  # Default

