"""Tests for mass properties calculation."""

import pytest

from src.geometry.mass_properties import MassPropertiesCalculator
from src.scene.scene_graph import Component, ComponentType, SceneGraph, Vector3D


def test_calculate_mass_simple():
    """Test mass calculation for simple component."""
    scene = SceneGraph()
    
    # Balsa stick: 1/8" x 1/4" x 12"
    component = Component(
        id="stick1",
        type=ComponentType.STICK,
        position=Vector3D(),
        dimensions={"width": 0.125, "height": 0.25, "length": 12.0},
        material_properties={"density_lb_per_in3": 0.008},
    )
    
    scene.add_component(component)
    
    calc = MassPropertiesCalculator()
    result = calc.calculate(scene)
    
    # Volume = 0.125 * 0.25 * 12 = 0.375 in³
    # Mass = 0.375 * 0.008 = 0.003 lb
    expected_mass = 0.125 * 0.25 * 12.0 * 0.008
    assert abs(result["total_mass_lb"] - expected_mass) < 0.0001


def test_calculate_cg():
    """Test center of gravity calculation."""
    scene = SceneGraph()
    
    # Two components at different positions
    comp1 = Component(
        id="comp1",
        type=ComponentType.STICK,
        position=Vector3D(x=0, y=0, z=0),
        dimensions={"width": 0.125, "height": 0.25, "length": 1.0},
        material_properties={"density_lb_per_in3": 0.008},
    )
    
    comp2 = Component(
        id="comp2",
        type=ComponentType.STICK,
        position=Vector3D(x=10, y=0, z=0),
        dimensions={"width": 0.125, "height": 0.25, "length": 1.0},
        material_properties={"density_lb_per_in3": 0.008},
    )
    
    scene.add_component(comp1)
    scene.add_component(comp2)
    
    calc = MassPropertiesCalculator()
    result = calc.calculate(scene)
    
    # CG should be at x=5 (midpoint) if masses are equal
    assert abs(result["cg"].x - 5.0) < 0.1


def test_fixed_mass_hardware():
    """Test mass calculation for hardware with fixed mass."""
    scene = SceneGraph()
    
    hardware = Component(
        id="hinge1",
        type=ComponentType.HARDWARE,
        position=Vector3D(),
        dimensions={},
        material_properties={"mass_lb": 0.001},
    )
    
    scene.add_component(hardware)
    
    calc = MassPropertiesCalculator()
    result = calc.calculate(scene)
    
    assert result["total_mass_lb"] == 0.001

