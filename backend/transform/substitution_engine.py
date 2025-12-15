"""
Substitution engine for component replacement.
"""

import io
import logging
from typing import Any, Optional

import ezdxf

from backend.shared.models import SceneGraph, SubstitutionRule, Component, ComponentType
from backend.component_db import ComponentCatalog

logger = logging.getLogger(__name__)


class SubstitutionEngine:
    """
    Engine for applying component substitutions.
    """
    
    def __init__(self, catalog: ComponentCatalog):
        self.catalog = catalog
    
    def apply_rules(
        self,
        dxf_bytes: bytes,
        scene_graph: SceneGraph,
        rules: list[SubstitutionRule],
    ) -> tuple[bytes, SceneGraph]:
        """
        Apply substitution rules to DXF and scene graph.
        
        Args:
            dxf_bytes: Input DXF as bytes
            scene_graph: Scene graph to modify
            rules: Rules to apply
            
        Returns:
            Tuple of (modified DXF bytes, modified scene graph)
        """
        # Load DXF
        doc = ezdxf.read(io.BytesIO(dxf_bytes))
        msp = doc.modelspace()
        
        for rule in rules:
            logger.info(f"Applying rule: {rule.description or rule.id}")
            
            # Find target components
            targets = self._find_targets(scene_graph, rule)
            
            for component in targets:
                self._apply_substitution(doc, msp, component, rule)
                self._update_scene_graph(scene_graph, component, rule)
        
        # Write modified DXF
        output = io.BytesIO()
        doc.write(output)
        output.seek(0)
        
        return output.read(), scene_graph
    
    def _find_targets(
        self,
        scene_graph: SceneGraph,
        rule: SubstitutionRule,
    ) -> list[Component]:
        """Find components matching the rule's target criteria."""
        targets = []
        
        for component in scene_graph.components:
            # Check specific component ID
            if rule.target_component_id and component.id != rule.target_component_id:
                continue
            
            # Check component type
            if rule.target_component_type and component.component_type != rule.target_component_type:
                continue
            
            # Check custom criteria
            if rule.target_criteria:
                if not self._matches_criteria(component, rule.target_criteria):
                    continue
            
            targets.append(component)
        
        return targets
    
    def _matches_criteria(self, component: Component, criteria: dict) -> bool:
        """Check if component matches custom criteria."""
        for key, value in criteria.items():
            if key == "material":
                if component.attributes.material and component.attributes.material.value != value:
                    return False
            elif key == "min_confidence":
                if component.classification_confidence < value:
                    return False
            elif key == "name_contains":
                if value.lower() not in (component.name or "").lower():
                    return False
        
        return True
    
    def _apply_substitution(
        self,
        doc: Any,
        msp: Any,
        component: Component,
        rule: SubstitutionRule,
    ):
        """Apply substitution to DXF entities."""
        # Find entities belonging to this component
        layer = component.dxf_layer
        
        if not layer:
            return
        
        # Get replacement specifications
        replacement = rule.replacement_attributes
        
        # If we have a catalog replacement, use its geometry
        if rule.replacement_catalog_id:
            catalog_comp = self.catalog.get(rule.replacement_catalog_id)
            if catalog_comp and catalog_comp.cross_section:
                # Modify cross-section dimensions
                replacement["cross_section"] = catalog_comp.cross_section
        
        # Apply geometric changes
        if "scale" in replacement:
            scale = replacement["scale"]
            # Would need to find and scale relevant entities
            logger.info(f"Would scale component {component.id} by {scale}")
        
        if "cross_section" in replacement:
            # Would need to modify cross-section representation
            logger.info(f"Would modify cross-section of {component.id}")
    
    def _update_scene_graph(
        self,
        scene_graph: SceneGraph,
        component: Component,
        rule: SubstitutionRule,
    ):
        """Update scene graph to reflect substitution."""
        # Update component attributes
        if rule.replacement_catalog_id:
            component.catalog_id = rule.replacement_catalog_id
            
            catalog_comp = self.catalog.get(rule.replacement_catalog_id)
            if catalog_comp:
                component.name = f"{component.name} → {catalog_comp.name}"
        
        # Update attributes from rule
        for key, value in rule.replacement_attributes.items():
            if hasattr(component.attributes, key):
                setattr(component.attributes, key, value)
            else:
                component.attributes.custom[key] = value
        
        # Add processing note
        scene_graph.add_processing_note(
            f"Substitution: {component.id} - {rule.description or 'Modified'}"
        )


