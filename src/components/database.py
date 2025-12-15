"""Component database for balsa model aircraft parts."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MaterialProperties(BaseModel):
    """Material properties for components."""
    density_lb_per_in3: float = Field(..., description="Density in pounds per cubic inch")
    strength_psi: Optional[float] = Field(None, description="Tensile strength in PSI")
    modulus_psi: Optional[float] = Field(None, description="Elastic modulus in PSI")


class ComponentSpec(BaseModel):
    """Specification for a component in the database."""
    id: str = Field(..., description="Unique component identifier")
    name: str = Field(..., description="Human-readable name")
    type: str = Field(..., description="Component type (stick, rib, spar, etc.)")
    dimensions: Dict[str, float] = Field(..., description="Dimensions (width, height, length, etc.)")
    material: str = Field(default="balsa", description="Material type")
    material_properties: MaterialProperties = Field(..., description="Material properties")
    mass_lb: Optional[float] = Field(None, description="Fixed mass if known")
    notes: Optional[str] = Field(None, description="Additional notes")


class ComponentDatabase:
    """Database of typical balsa model aircraft components."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize component database.
        
        Args:
            db_path: Path to JSON database file (defaults to data/components.json)
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "components.json"
        
        self.db_path = Path(db_path)
        self.components: Dict[str, ComponentSpec] = {}
        self._load_database()

    def _load_database(self):
        """Load component database from JSON file."""
        if self.db_path.exists():
            with open(self.db_path, "r") as f:
                data = json.load(f)
                for comp_data in data.get("components", []):
                    comp = ComponentSpec(**comp_data)
                    self.components[comp.id] = comp
        else:
            # Initialize with default data
            self._initialize_default_data()
            self._save_database()

    def _save_database(self):
        """Save component database to JSON file."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "components": [comp.dict() for comp in self.components.values()],
        }
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _initialize_default_data(self):
        """Initialize database with typical balsa model components."""
        # Balsa density: ~0.005-0.015 lb/in³ (typical ~0.008)
        balsa_density = 0.008
        
        # Common balsa stick sizes
        stick_sizes = [
            ("1/16", "1/8", "1/16 x 1/8"),
            ("1/16", "1/4", "1/16 x 1/4"),
            ("1/8", "1/8", "1/8 x 1/8"),
            ("1/8", "1/4", "1/8 x 1/4"),
            ("1/8", "3/8", "1/8 x 3/8"),
            ("3/16", "1/4", "3/16 x 1/4"),
            ("3/16", "3/8", "3/16 x 3/8"),
            ("1/4", "1/4", "1/4 x 1/4"),
            ("1/4", "3/8", "1/4 x 3/8"),
        ]
        
        for width_frac, height_frac, name in stick_sizes:
            width = self._parse_fraction(width_frac)
            height = self._parse_fraction(height_frac)
            
            comp_id = f"stick_{width_frac.replace('/', '_')}_x_{height_frac.replace('/', '_')}"
            comp = ComponentSpec(
                id=comp_id,
                name=f"Balsa Stick {name}",
                type="stick",
                dimensions={"width": width, "height": height, "length": 12.0},  # Default 12" length
                material="balsa",
                material_properties=MaterialProperties(density_lb_per_in3=balsa_density),
            )
            self.components[comp_id] = comp
        
        # Sheeting sizes
        sheet_thicknesses = ["1/32", "1/16", "3/32", "1/8"]
        for thickness_frac in sheet_thicknesses:
            thickness = self._parse_fraction(thickness_frac)
            comp_id = f"sheeting_{thickness_frac.replace('/', '_')}"
            comp = ComponentSpec(
                id=comp_id,
                name=f"Balsa Sheeting {thickness_frac}",
                type="sheeting",
                dimensions={"thickness": thickness, "width": 3.0, "length": 12.0},
                material="balsa",
                material_properties=MaterialProperties(density_lb_per_in3=balsa_density),
            )
            self.components[comp_id] = comp
        
        # Hardware (approximate masses)
        hardware = [
            ("hinge_standard", "Standard Hinge", 0.001),  # ~1 gram
            ("control_horn_standard", "Standard Control Horn", 0.002),
            ("pushrod_connector", "Pushrod Connector", 0.0005),
        ]
        
        for hw_id, hw_name, mass_lb in hardware:
            comp = ComponentSpec(
                id=hw_id,
                name=hw_name,
                type="hardware",
                dimensions={},
                material="plastic/metal",
                material_properties=MaterialProperties(density_lb_per_in3=0.0),  # Fixed mass
                mass_lb=mass_lb,
            )
            self.components[hw_id] = comp

    def _parse_fraction(self, frac_str: str) -> float:
        """Parse fraction string to float."""
        if "/" in frac_str:
            num, den = frac_str.split("/")
            return float(num) / float(den)
        else:
            return float(frac_str)

    def get_component(self, component_id: str) -> Optional[ComponentSpec]:
        """Get component by ID."""
        return self.components.get(component_id)

    def find_compatible_replacements(
        self, component_type: str, constraints: Optional[Dict] = None
    ) -> List[ComponentSpec]:
        """
        Find compatible replacement components.
        
        Args:
            component_type: Type of component to replace
            constraints: Optional constraints (min_width, max_width, etc.)
        
        Returns:
            List of compatible ComponentSpec objects
        """
        candidates = [
            comp for comp in self.components.values() if comp.type == component_type
        ]
        
        if constraints:
            filtered = []
            for comp in candidates:
                if self._matches_constraints(comp, constraints):
                    filtered.append(comp)
            return filtered
        
        return candidates

    def _matches_constraints(self, comp: ComponentSpec, constraints: Dict) -> bool:
        """Check if component matches constraints."""
        dims = comp.dimensions
        
        if "min_width" in constraints and dims.get("width", 0) < constraints["min_width"]:
            return False
        if "max_width" in constraints and dims.get("width", 0) > constraints["max_width"]:
            return False
        if "min_height" in constraints and dims.get("height", 0) < constraints["min_height"]:
            return False
        if "max_height" in constraints and dims.get("height", 0) > constraints["max_height"]:
            return False
        
        return True

    def add_component(self, component: ComponentSpec):
        """Add a new component to the database."""
        self.components[component.id] = component
        self._save_database()

