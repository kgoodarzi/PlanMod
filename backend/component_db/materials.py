"""
Material database for PlanMod.

Contains physical properties of materials.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MaterialProperties:
    """Physical properties of a material."""
    
    name: str
    density_kg_m3: float
    
    # Strength properties (optional)
    tensile_strength_mpa: Optional[float] = None
    compressive_strength_mpa: Optional[float] = None
    modulus_gpa: Optional[float] = None
    
    # Notes
    grain_direction: Optional[str] = None  # "along", "across", "none"
    notes: str = ""


class MaterialDatabase:
    """
    Database of material properties.
    """
    
    MATERIALS = {
        # Wood
        "balsa_soft": MaterialProperties(
            name="Balsa (Soft/Light)",
            density_kg_m3=100,
            tensile_strength_mpa=7,
            compressive_strength_mpa=4,
            modulus_gpa=2.5,
            grain_direction="along",
            notes="A-grain, contest quality",
        ),
        "balsa_medium": MaterialProperties(
            name="Balsa (Medium)",
            density_kg_m3=160,
            tensile_strength_mpa=14,
            compressive_strength_mpa=8,
            modulus_gpa=4.0,
            grain_direction="along",
            notes="Standard hobby grade",
        ),
        "balsa_hard": MaterialProperties(
            name="Balsa (Hard/Dense)",
            density_kg_m3=220,
            tensile_strength_mpa=21,
            compressive_strength_mpa=12,
            modulus_gpa=5.5,
            grain_direction="along",
            notes="C-grain, structural",
        ),
        "basswood": MaterialProperties(
            name="Basswood",
            density_kg_m3=420,
            tensile_strength_mpa=50,
            compressive_strength_mpa=30,
            modulus_gpa=10,
            grain_direction="along",
        ),
        "spruce": MaterialProperties(
            name="Spruce",
            density_kg_m3=450,
            tensile_strength_mpa=70,
            compressive_strength_mpa=35,
            modulus_gpa=12,
            grain_direction="along",
            notes="Aircraft grade",
        ),
        "birch_plywood": MaterialProperties(
            name="Birch Plywood",
            density_kg_m3=680,
            tensile_strength_mpa=80,
            compressive_strength_mpa=50,
            modulus_gpa=13,
            grain_direction="none",
            notes="Aircraft grade, void-free",
        ),
        "lite_ply": MaterialProperties(
            name="Lite-Ply",
            density_kg_m3=400,
            tensile_strength_mpa=40,
            compressive_strength_mpa=25,
            modulus_gpa=6,
            grain_direction="none",
            notes="Poplar core",
        ),
        
        # Composites
        "carbon_fiber": MaterialProperties(
            name="Carbon Fiber",
            density_kg_m3=1600,
            tensile_strength_mpa=600,
            modulus_gpa=70,
            notes="Unidirectional tape/tube",
        ),
        "fiberglass": MaterialProperties(
            name="Fiberglass",
            density_kg_m3=1800,
            tensile_strength_mpa=200,
            modulus_gpa=20,
        ),
        
        # Foam
        "epp": MaterialProperties(
            name="EPP Foam",
            density_kg_m3=30,
            notes="Expanded polypropylene, crash resistant",
        ),
        "eps": MaterialProperties(
            name="EPS Foam",
            density_kg_m3=20,
            notes="Expanded polystyrene",
        ),
        "depron": MaterialProperties(
            name="Depron",
            density_kg_m3=40,
            notes="Extruded polystyrene sheet",
        ),
        
        # Metals
        "aluminum": MaterialProperties(
            name="Aluminum",
            density_kg_m3=2700,
            tensile_strength_mpa=270,
            modulus_gpa=70,
        ),
        "steel": MaterialProperties(
            name="Steel",
            density_kg_m3=7850,
            tensile_strength_mpa=400,
            modulus_gpa=200,
        ),
        
        # Plastics
        "nylon": MaterialProperties(
            name="Nylon",
            density_kg_m3=1150,
            tensile_strength_mpa=70,
            modulus_gpa=3,
        ),
        "abs": MaterialProperties(
            name="ABS Plastic",
            density_kg_m3=1050,
            tensile_strength_mpa=40,
            modulus_gpa=2.3,
        ),
    }
    
    @classmethod
    def get(cls, material_id: str) -> Optional[MaterialProperties]:
        """Get material properties by ID."""
        return cls.MATERIALS.get(material_id.lower().replace(" ", "_"))
    
    @classmethod
    def get_density(cls, material_id: str) -> float:
        """Get material density in kg/m³."""
        mat = cls.get(material_id)
        return mat.density_kg_m3 if mat else 160  # Default to medium balsa
    
    @classmethod
    def list_materials(cls) -> list[str]:
        """List all material IDs."""
        return list(cls.MATERIALS.keys())
    
    @classmethod
    def calculate_mass(
        cls,
        material_id: str,
        volume_mm3: float,
    ) -> float:
        """
        Calculate mass from volume.
        
        Args:
            material_id: Material identifier
            volume_mm3: Volume in cubic millimeters
            
        Returns:
            Mass in grams
        """
        density = cls.get_density(material_id)
        # Convert mm³ to m³, multiply by density (kg/m³), convert to grams
        volume_m3 = volume_mm3 / 1e9
        mass_kg = volume_m3 * density
        return mass_kg * 1000  # grams


