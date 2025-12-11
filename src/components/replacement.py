"""Component replacement logic with structural integrity heuristics."""

from typing import Dict, Optional

from .database import ComponentDatabase, ComponentSpec
from ..scene.scene_graph import Component, SceneGraph


class ReplacementEngine:
    """Engine for replacing components while maintaining structural integrity."""

    def __init__(self, component_db: ComponentDatabase):
        """
        Initialize replacement engine.
        
        Args:
            component_db: ComponentDatabase instance
        """
        self.component_db = component_db

    def replace_component(
        self,
        scene: SceneGraph,
        component_id: str,
        replacement_spec_id: str,
    ) -> SceneGraph:
        """
        Replace a component in the scene graph.
        
        Args:
            scene: Scene graph to modify
            component_id: ID of component to replace
            replacement_spec_id: ID of replacement component from database
        
        Returns:
            Modified scene graph
        """
        component = scene.get_component(component_id)
        if not component:
            raise ValueError(f"Component not found: {component_id}")
        
        replacement_spec = self.component_db.get_component(replacement_spec_id)
        if not replacement_spec:
            raise ValueError(f"Replacement spec not found: {replacement_spec_id}")
        
        # Update component properties
        component.type = replacement_spec.type
        component.material = replacement_spec.material
        component.material_properties = replacement_spec.material_properties.dict()
        
        # Update dimensions (preserve length if applicable)
        old_dims = component.dimensions.copy()
        new_dims = replacement_spec.dimensions.copy()
        
        # Preserve length for sticks/spars
        if "length" in old_dims and "length" in new_dims:
            new_dims["length"] = old_dims["length"]
        
        component.dimensions = new_dims
        
        # Apply structural adjustments to dependent components
        self._adjust_dependent_components(scene, component, old_dims, new_dims)
        
        return scene

    def _adjust_dependent_components(
        self,
        scene: SceneGraph,
        component: Component,
        old_dims: Dict,
        new_dims: Dict,
    ):
        """
        Adjust dependent components to maintain structural integrity.
        
        Simple heuristics for MVP:
        - If a spar/stick gets thicker, adjust rib/former cutouts
        - If dimensions change, adjust plate holes/slots
        """
        # Check if width or height changed significantly
        width_change = new_dims.get("width", 0) - old_dims.get("width", 0)
        height_change = new_dims.get("height", 0) - old_dims.get("height", 0)
        
        threshold = 0.01  # 0.01" change threshold
        
        if abs(width_change) < threshold and abs(height_change) < threshold:
            return  # No significant change
        
        # Adjust child components (ribs, formers that attach to this component)
        for child_id in component.children_ids:
            child = scene.get_component(child_id)
            if not child:
                continue
            
            if child.type in ["rib", "former"]:
                # Adjust cutout dimensions in ribs/formers
                if "cutout_width" in child.dimensions:
                    child.dimensions["cutout_width"] += width_change
                if "cutout_height" in child.dimensions:
                    child.dimensions["cutout_height"] += height_change
                
                # Ensure cutout doesn't become negative
                child.dimensions["cutout_width"] = max(0, child.dimensions.get("cutout_width", 0))
                child.dimensions["cutout_height"] = max(0, child.dimensions.get("cutout_height", 0))
            
            elif child.type in ["plate", "sheeting"]:
                # Adjust hole/slot positions if needed
                # For MVP, just log that adjustment may be needed
                pass

