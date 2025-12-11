"""Tests for component database."""

import tempfile
from pathlib import Path

import pytest

from src.components.database import ComponentDatabase, ComponentSpec, MaterialProperties


def test_component_database_initialization():
    """Test database initialization with default data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "components.json"
        db = ComponentDatabase(db_path=db_path)
        
        # Should have default components
        assert len(db.components) > 0
        
        # Check for common stick sizes
        stick = db.get_component("stick_1_16_x_1_8")
        assert stick is not None
        assert stick.type == "stick"
        assert stick.dimensions["width"] == 1/16
        assert stick.dimensions["height"] == 1/8


def test_find_compatible_replacements():
    """Test finding compatible replacement components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "components.json"
        db = ComponentDatabase(db_path=db_path)
        
        # Find all sticks
        sticks = db.find_compatible_replacements("stick")
        assert len(sticks) > 0
        
        # Find sticks with constraints
        large_sticks = db.find_compatible_replacements(
            "stick", constraints={"min_width": 0.125}
        )
        assert all(s.dimensions.get("width", 0) >= 0.125 for s in large_sticks)


def test_add_component():
    """Test adding a custom component."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "components.json"
        db = ComponentDatabase(db_path=db_path)
        
        custom = ComponentSpec(
            id="custom_stick",
            name="Custom Stick",
            type="stick",
            dimensions={"width": 0.2, "height": 0.3, "length": 10.0},
            material_properties=MaterialProperties(density_lb_per_in3=0.01),
        )
        
        db.add_component(custom)
        
        assert db.get_component("custom_stick") == custom
        assert db_path.exists()

