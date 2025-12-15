"""
Component catalog for PlanMod.

Contains definitions of standard components and their properties.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ComponentDefinition:
    """Definition of a catalog component."""
    
    id: str
    name: str
    component_type: str
    category: str
    
    # Geometry
    cross_section: Optional[dict] = None
    default_length: Optional[float] = None  # mm
    
    # Material
    material: str = "unknown"
    material_grade: Optional[str] = None
    
    # Physical properties
    mass_per_length: Optional[float] = None  # g/mm
    mass_per_area: Optional[float] = None    # g/mm²
    mass_per_unit: Optional[float] = None    # g
    
    # DXF
    dxf_block_name: Optional[str] = None
    
    # Metadata
    description: str = ""
    tags: list[str] = field(default_factory=list)
    substitutes: list[str] = field(default_factory=list)
    
    def get_mass(self, length: Optional[float] = None, area: Optional[float] = None) -> float:
        """Calculate mass based on dimensions."""
        if self.mass_per_unit:
            return self.mass_per_unit
        if length and self.mass_per_length:
            return length * self.mass_per_length
        if area and self.mass_per_area:
            return area * self.mass_per_area
        return 0.0


class ComponentCatalog:
    """
    Catalog of standard components for model aircraft.
    
    Categories:
    - balsa_stock: Sheets and sticks
    - plywood: Plywood sheets
    - hardware: Fasteners, hinges, etc.
    - motors: Electric motors
    - propellers: Propellers
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize component catalog.
        
        Args:
            data_dir: Directory containing catalog JSON files
        """
        self.data_dir = data_dir or (Path(__file__).parent / "data")
        self.components: dict[str, ComponentDefinition] = {}
        
        self._load_catalog()
    
    def _load_catalog(self):
        """Load catalog from JSON files."""
        # Load built-in catalog
        self._load_balsa_stock()
        self._load_plywood()
        self._load_hardware()
        
        # Load from data directory if exists
        if self.data_dir.exists():
            for json_file in self.data_dir.glob("*.json"):
                try:
                    self._load_json_file(json_file)
                except Exception as e:
                    logger.warning(f"Failed to load {json_file}: {e}")
        
        logger.info(f"Loaded {len(self.components)} components into catalog")
    
    def _load_json_file(self, filepath: Path):
        """Load components from a JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        
        for comp_data in data.get("components", []):
            comp = ComponentDefinition(**comp_data)
            self.components[comp.id] = comp
    
    def _load_balsa_stock(self):
        """Load built-in balsa stock definitions."""
        # Standard balsa sheet sizes (inches)
        sheet_thicknesses = [
            (1/32, "1/32"),
            (1/16, "1/16"),
            (3/32, "3/32"),
            (1/8, "1/8"),
            (3/16, "3/16"),
            (1/4, "1/4"),
        ]
        
        for thickness_in, thickness_str in sheet_thicknesses:
            thickness_mm = thickness_in * 25.4
            density = 160  # kg/m³ for medium balsa
            
            comp = ComponentDefinition(
                id=f"BALSA_SHEET_{thickness_str.replace('/', '_')}",
                name=f"{thickness_str}\" Balsa Sheet",
                component_type="sheet",
                category="balsa_stock",
                material="balsa",
                cross_section={"type": "sheet", "thickness_mm": thickness_mm},
                mass_per_area=thickness_mm * density / 1000,  # g/mm²
                description=f"Standard {thickness_str}\" balsa sheet",
                tags=["balsa", "sheet", "wood"],
            )
            self.components[comp.id] = comp
        
        # Standard balsa stick sizes
        stick_sizes = [
            (1/16, 1/16, "1/16 SQ"),
            (1/8, 1/8, "1/8 SQ"),
            (3/16, 3/16, "3/16 SQ"),
            (1/4, 1/4, "1/4 SQ"),
            (1/8, 1/4, "1/8 x 1/4"),
            (1/4, 1/2, "1/4 x 1/2"),
            (1/4, 1, "1/4 x 1"),
        ]
        
        for w_in, h_in, name in stick_sizes:
            w_mm = w_in * 25.4
            h_mm = h_in * 25.4
            density = 160
            area_mm2 = w_mm * h_mm
            
            comp = ComponentDefinition(
                id=f"BALSA_STICK_{name.replace(' ', '_').replace('/', '_')}",
                name=f"{name} Balsa Stick",
                component_type="stick",
                category="balsa_stock",
                material="balsa",
                cross_section={"type": "rectangle", "width_mm": w_mm, "height_mm": h_mm},
                mass_per_length=area_mm2 * density / 1e6,  # g/mm
                description=f"Standard {name} balsa stick",
                tags=["balsa", "stick", "wood"],
            )
            self.components[comp.id] = comp
    
    def _load_plywood(self):
        """Load built-in plywood definitions."""
        ply_thicknesses = [
            (1.5, "1.5mm"),
            (2.0, "2mm"),
            (3.0, "3mm"),
            (4.0, "4mm"),
            (6.0, "6mm"),
        ]
        
        density = 680  # kg/m³ for birch plywood
        
        for thickness_mm, name in ply_thicknesses:
            comp = ComponentDefinition(
                id=f"PLY_{name.replace('.', '_')}",
                name=f"{name} Plywood",
                component_type="sheet",
                category="plywood",
                material="plywood",
                cross_section={"type": "sheet", "thickness_mm": thickness_mm},
                mass_per_area=thickness_mm * density / 1000,
                description=f"Aircraft grade {name} birch plywood",
                tags=["plywood", "sheet", "wood"],
            )
            self.components[comp.id] = comp
    
    def _load_hardware(self):
        """Load built-in hardware definitions."""
        # Hinges
        hinges = [
            ("HINGE_NYLON_SM", "Small Nylon Hinge", 0.3),
            ("HINGE_NYLON_MED", "Medium Nylon Hinge", 0.5),
            ("HINGE_NYLON_LG", "Large Nylon Hinge", 0.8),
            ("HINGE_CA", "CA Hinge", 0.1),
        ]
        
        for id_, name, mass in hinges:
            comp = ComponentDefinition(
                id=id_,
                name=name,
                component_type="hinge",
                category="hardware",
                material="nylon",
                mass_per_unit=mass,
                description=f"Standard {name.lower()}",
                tags=["hinge", "hardware", "control_surface"],
            )
            self.components[comp.id] = comp
        
        # Control horns
        horns = [
            ("HORN_NYLON_SM", "Small Nylon Control Horn", 1.0),
            ("HORN_NYLON_MED", "Medium Nylon Control Horn", 2.0),
            ("HORN_NYLON_LG", "Large Nylon Control Horn", 3.5),
        ]
        
        for id_, name, mass in horns:
            comp = ComponentDefinition(
                id=id_,
                name=name,
                component_type="hardware",
                category="hardware",
                material="nylon",
                mass_per_unit=mass,
                description=f"Standard {name.lower()}",
                tags=["control_horn", "hardware", "control"],
            )
            self.components[comp.id] = comp
    
    def get(self, component_id: str) -> Optional[ComponentDefinition]:
        """Get component by ID."""
        return self.components.get(component_id)
    
    def search(
        self,
        query: Optional[str] = None,
        component_type: Optional[str] = None,
        category: Optional[str] = None,
        material: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[ComponentDefinition]:
        """
        Search catalog for components.
        
        Args:
            query: Text search in name/description
            component_type: Filter by component type
            category: Filter by category
            material: Filter by material
            tags: Filter by tags (any match)
            
        Returns:
            List of matching components
        """
        results = list(self.components.values())
        
        if query:
            query_lower = query.lower()
            results = [
                c for c in results
                if query_lower in c.name.lower() or query_lower in c.description.lower()
            ]
        
        if component_type:
            results = [c for c in results if c.component_type == component_type]
        
        if category:
            results = [c for c in results if c.category == category]
        
        if material:
            results = [c for c in results if c.material == material]
        
        if tags:
            results = [c for c in results if any(t in c.tags for t in tags)]
        
        return results
    
    def find_substitutes(self, component_id: str) -> list[ComponentDefinition]:
        """Find substitute components for a given component."""
        comp = self.get(component_id)
        if not comp:
            return []
        
        substitutes = []
        
        # Get explicitly listed substitutes
        for sub_id in comp.substitutes:
            sub = self.get(sub_id)
            if sub:
                substitutes.append(sub)
        
        # Find similar components
        similar = self.search(
            component_type=comp.component_type,
            material=comp.material,
        )
        
        for sim in similar:
            if sim.id != component_id and sim not in substitutes:
                substitutes.append(sim)
        
        return substitutes
    
    def get_summary(self) -> str:
        """Get a text summary of the catalog for LLM context."""
        lines = ["Component Catalog Summary:", ""]
        
        # Group by category
        by_category: dict[str, list[ComponentDefinition]] = {}
        for comp in self.components.values():
            if comp.category not in by_category:
                by_category[comp.category] = []
            by_category[comp.category].append(comp)
        
        for category, comps in sorted(by_category.items()):
            lines.append(f"## {category.replace('_', ' ').title()}")
            for comp in comps[:10]:  # Limit per category
                lines.append(f"- {comp.id}: {comp.name}")
            if len(comps) > 10:
                lines.append(f"  ... and {len(comps) - 10} more")
            lines.append("")
        
        return "\n".join(lines)


