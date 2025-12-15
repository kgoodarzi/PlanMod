"""
Component classification for PlanMod.

Uses VLM to classify components within drawing regions.
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image

from backend.vlm_client.base import VLMClient, ComponentClassification

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedComponent:
    """A classified component with bounds."""
    
    component_type: str
    confidence: float
    description: str
    suggested_name: str = ""
    material: Optional[str] = None
    dimensions: Optional[dict] = None
    bounds: Optional["ComponentBounds"] = None
    alternatives: list[str] = field(default_factory=list)


@dataclass
class ComponentBounds:
    """Bounding box for a component within its region."""
    
    x: float
    y: float
    width: float
    height: float


class ComponentClassifier:
    """
    Classifies components within drawing regions.
    
    Uses VLM to:
    - Identify component types
    - Suggest names/IDs
    - Estimate materials
    - Extract dimensions
    """
    
    # Common component types for model aircraft
    AIRCRAFT_COMPONENT_TYPES = [
        "rib",
        "former",
        "bulkhead",
        "spar",
        "stringer",
        "longeron",
        "skin",
        "covering",
        "aileron",
        "elevator",
        "rudder",
        "flap",
        "wing",
        "fuselage",
        "tail",
        "motor_mount",
        "firewall",
        "landing_gear",
        "wheel",
        "fastener",
        "hinge",
    ]
    
    def __init__(self, vlm_client: VLMClient):
        """
        Initialize component classifier.
        
        Args:
            vlm_client: VLM client for image analysis
        """
        self.vlm_client = vlm_client
    
    async def classify_region(
        self,
        region_image: np.ndarray,
        region_type: str,
        max_components: int = 20,
    ) -> list[ClassifiedComponent]:
        """
        Classify all components in a region.
        
        Args:
            region_image: Cropped image of the region
            region_type: Type of region (e.g., "side_view")
            max_components: Maximum components to identify
            
        Returns:
            List of classified components
        """
        logger.info(f"Classifying components in {region_type} region")
        
        # Convert to bytes
        image_bytes = self._image_to_bytes(region_image)
        
        # Build context
        context = f"This is a {region_type} from a model aircraft drawing. "
        context += "Identify the major structural and mechanical components visible."
        
        # Get classification from VLM
        response = await self.vlm_client.classify_component(
            image_bytes,
            context,
            self.AIRCRAFT_COMPONENT_TYPES,
        )
        
        if not response.success:
            logger.warning(f"Component classification failed: {response.error}")
            return []
        
        # Convert VLM components to ClassifiedComponent
        components = []
        
        for vlm_comp in response.components:
            comp = ClassifiedComponent(
                component_type=vlm_comp.component_type,
                confidence=vlm_comp.confidence,
                description=vlm_comp.description,
                suggested_name=vlm_comp.suggested_name,
                material=vlm_comp.material,
                dimensions=vlm_comp.dimensions,
                alternatives=vlm_comp.alternatives,
            )
            components.append(comp)
        
        # If VLM returned structured data with multiple components
        if response.structured_data and "components" in response.structured_data:
            for comp_data in response.structured_data["components"]:
                comp = ClassifiedComponent(
                    component_type=comp_data.get("type", "unknown"),
                    confidence=comp_data.get("confidence", 0.5),
                    description=comp_data.get("description", ""),
                    suggested_name=comp_data.get("name", ""),
                    material=comp_data.get("material"),
                    dimensions=comp_data.get("dimensions"),
                )
                
                if "bounds" in comp_data:
                    b = comp_data["bounds"]
                    comp.bounds = ComponentBounds(
                        x=b.get("x", 0) / 100,  # Convert percentage to fraction
                        y=b.get("y", 0) / 100,
                        width=b.get("width", 10) / 100,
                        height=b.get("height", 10) / 100,
                    )
                
                components.append(comp)
        
        # Limit to max_components
        components = components[:max_components]
        
        logger.info(f"Classified {len(components)} components")
        
        return components
    
    async def classify_single(
        self,
        component_image: np.ndarray,
        context: str = "",
    ) -> ClassifiedComponent:
        """
        Classify a single component.
        
        Args:
            component_image: Image of the component
            context: Additional context
            
        Returns:
            Classified component
        """
        image_bytes = self._image_to_bytes(component_image)
        
        response = await self.vlm_client.classify_component(
            image_bytes,
            context or "Identify this component from a model aircraft drawing.",
            self.AIRCRAFT_COMPONENT_TYPES,
        )
        
        if response.success and response.components:
            vlm_comp = response.components[0]
            return ClassifiedComponent(
                component_type=vlm_comp.component_type,
                confidence=vlm_comp.confidence,
                description=vlm_comp.description,
                suggested_name=vlm_comp.suggested_name,
                material=vlm_comp.material,
                dimensions=vlm_comp.dimensions,
                alternatives=vlm_comp.alternatives,
            )
        
        return ClassifiedComponent(
            component_type="unknown",
            confidence=0.0,
            description="Classification failed",
        )
    
    def _image_to_bytes(self, image: np.ndarray) -> bytes:
        """Convert numpy image to PNG bytes."""
        pil_image = Image.fromarray(image)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    
    async def group_components(
        self,
        components: list[ClassifiedComponent],
        region_type: str,
    ) -> dict[str, list[ClassifiedComponent]]:
        """
        Group components by their functional role.
        
        Args:
            components: List of classified components
            region_type: Type of the region
            
        Returns:
            Dictionary mapping group names to component lists
        """
        groups: dict[str, list[ClassifiedComponent]] = {
            "structural": [],
            "control_surfaces": [],
            "hardware": [],
            "covering": [],
            "other": [],
        }
        
        structural_types = {"rib", "former", "bulkhead", "spar", "stringer", "longeron"}
        control_types = {"aileron", "elevator", "rudder", "flap"}
        hardware_types = {"fastener", "hinge", "motor_mount", "firewall", "landing_gear", "wheel"}
        covering_types = {"skin", "covering"}
        
        for comp in components:
            comp_type = comp.component_type.lower()
            
            if comp_type in structural_types:
                groups["structural"].append(comp)
            elif comp_type in control_types:
                groups["control_surfaces"].append(comp)
            elif comp_type in hardware_types:
                groups["hardware"].append(comp)
            elif comp_type in covering_types:
                groups["covering"].append(comp)
            else:
                groups["other"].append(comp)
        
        return groups


