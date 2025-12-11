"""Calculate mass and center of gravity for scene graph."""

from typing import Dict

from ..scene.scene_graph import Component, SceneGraph, Vector3D


class MassPropertiesCalculator:
    """Calculate mass properties from scene graph."""

    def calculate(self, scene: SceneGraph) -> Dict:
        """
        Calculate total mass and center of gravity.
        
        Returns:
            Dictionary with:
            - total_mass_lb: Total mass in pounds
            - cg: Center of gravity (Vector3D)
            - component_masses: Dictionary mapping component IDs to masses
        """
        total_mass = 0.0
        weighted_cg = Vector3D()
        component_masses = {}
        
        for component in scene.components.values():
            mass = self._calculate_component_mass(component)
            component_masses[component.id] = mass
            total_mass += mass
            
            # Add to weighted CG
            weighted_cg.x += mass * component.position.x
            weighted_cg.y += mass * component.position.y
            weighted_cg.z += mass * component.position.z
        
        # Calculate CG
        if total_mass > 0:
            cg = Vector3D(
                x=weighted_cg.x / total_mass,
                y=weighted_cg.y / total_mass,
                z=weighted_cg.z / total_mass,
            )
        else:
            cg = Vector3D()
        
        return {
            "total_mass_lb": total_mass,
            "cg": cg,
            "component_masses": component_masses,
        }

    def _calculate_component_mass(self, component: Component) -> float:
        """Calculate mass of a single component."""
        dims = component.dimensions
        
        # Check for fixed mass (hardware)
        if "mass_lb" in component.material_properties:
            return component.material_properties["mass_lb"]
        
        # Calculate volume
        volume = self._calculate_volume(component)
        
        # Get density
        density = component.material_properties.get("density_lb_per_in3", 0.008)  # Default balsa
        
        return volume * density

    def _calculate_volume(self, component: Component) -> float:
        """Calculate volume of component from dimensions."""
        dims = component.dimensions
        comp_type = component.type
        
        if comp_type in ["stick", "spar", "longeron", "stringer"]:
            # Rectangular cross-section
            width = dims.get("width", 0)
            height = dims.get("height", 0)
            length = dims.get("length", 1.0)
            return width * height * length
        
        elif comp_type in ["rib", "former"]:
            # Approximate as plate with area and thickness
            area = dims.get("area", 0)
            thickness = dims.get("thickness", 0.0625)  # Default 1/16"
            if area == 0:
                # Fallback: use width x height
                width = dims.get("width", 0)
                height = dims.get("height", 0)
                area = width * height
            return area * thickness
        
        elif comp_type in ["plate", "sheeting"]:
            # Flat panel
            width = dims.get("width", 0)
            length = dims.get("length", 0)
            thickness = dims.get("thickness", 0.0625)
            return width * length * thickness
        
        elif comp_type == "hardware":
            # Use fixed mass if available
            return 0.0  # Volume not used for hardware
        
        else:
            # Default: assume small rectangular volume
            width = dims.get("width", 0.125)
            height = dims.get("height", 0.125)
            length = dims.get("length", 1.0)
            return width * height * length

