"""
Mass and center of gravity calculator.
"""

import logging
from typing import Any, Optional

from backend.shared.models import SceneGraph, Component
from backend.component_db import ComponentCatalog, MaterialDatabase

logger = logging.getLogger(__name__)


class MassCalculator:
    """
    Calculates mass and center of gravity from scene graph.
    """
    
    def __init__(self, catalog: ComponentCatalog):
        self.catalog = catalog
    
    def calculate(self, scene_graph: SceneGraph) -> dict:
        """
        Calculate total mass and CG from scene graph components.
        
        Args:
            scene_graph: Scene graph with components
            
        Returns:
            Dictionary with mass analysis results
        """
        total_mass_g = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        
        component_masses = []
        
        for component in scene_graph.components:
            mass = self._estimate_component_mass(component)
            
            if mass > 0:
                # Get component center
                cx, cy = component.bounds.center
                
                total_mass_g += mass
                weighted_x += mass * cx
                weighted_y += mass * cy
                
                component_masses.append({
                    "id": component.id,
                    "name": component.name,
                    "type": component.component_type.value,
                    "mass_g": mass,
                    "position": (cx, cy),
                })
        
        # Calculate CG
        cg_x = weighted_x / total_mass_g if total_mass_g > 0 else 0
        cg_y = weighted_y / total_mass_g if total_mass_g > 0 else 0
        
        result = {
            "total_mass_g": total_mass_g,
            "total_mass_kg": total_mass_g / 1000,
            "center_of_gravity": (cg_x, cg_y),
            "component_masses": component_masses,
        }
        
        logger.info(f"Calculated mass: {total_mass_g:.1f}g, CG: ({cg_x:.1f}, {cg_y:.1f})")
        
        return result
    
    def _estimate_component_mass(self, component: Component) -> float:
        """
        Estimate mass of a single component.
        
        Args:
            component: Component to estimate
            
        Returns:
            Estimated mass in grams
        """
        # Try catalog lookup first
        if component.catalog_id:
            catalog_comp = self.catalog.get(component.catalog_id)
            if catalog_comp:
                # Calculate based on catalog properties
                if catalog_comp.mass_per_unit:
                    return catalog_comp.mass_per_unit
                
                if catalog_comp.mass_per_length and component.attributes.length:
                    length_mm = component.attributes.length.to_mm()
                    return catalog_comp.mass_per_length * length_mm
                
                if catalog_comp.mass_per_area:
                    area_mm2 = component.bounds.width * component.bounds.height
                    return catalog_comp.mass_per_area * area_mm2
        
        # Fall back to material-based estimation
        material = component.attributes.material
        if material:
            density = MaterialDatabase.get_density(material.value)
        else:
            density = 160  # Default to medium balsa
        
        # Estimate volume from bounds and typical thickness
        width_mm = component.bounds.width
        height_mm = component.bounds.height
        
        # Estimate thickness based on component type
        thickness_mm = self._estimate_thickness(component)
        
        volume_mm3 = width_mm * height_mm * thickness_mm * 0.5  # Rough shape factor
        
        # Calculate mass
        mass_g = MaterialDatabase.calculate_mass(
            material.value if material else "balsa_medium",
            volume_mm3,
        )
        
        return mass_g
    
    def _estimate_thickness(self, component: Component) -> float:
        """Estimate typical thickness for component type."""
        from backend.shared.models import ComponentType
        
        thickness_map = {
            ComponentType.RIB: 3.0,        # 3mm typical rib
            ComponentType.FORMER: 3.0,     # 3mm typical former
            ComponentType.BULKHEAD: 6.0,   # 6mm plywood bulkhead
            ComponentType.SPAR: 6.0,       # 1/4" square typical
            ComponentType.STRINGER: 3.0,   # 1/8" square typical
            ComponentType.LONGERON: 6.0,
            ComponentType.SKIN: 1.5,       # 1/16" balsa
            ComponentType.COVERING: 0.5,   # Film/tissue
        }
        
        if component.attributes.thickness:
            return component.attributes.thickness.to_mm()
        
        return thickness_map.get(component.component_type, 3.0)


