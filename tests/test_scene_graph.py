"""Tests for scene graph construction."""

import pytest

from src.scene.scene_graph import Component, ComponentType, SceneGraph, Vector3D


def test_scene_graph_creation():
    """Test creating a scene graph."""
    scene = SceneGraph()
    
    component = Component(
        id="test_1",
        type=ComponentType.SPAR,
        position=Vector3D(x=1.0, y=2.0, z=3.0),
        dimensions={"width": 0.125, "height": 0.25, "length": 12.0},
    )
    
    scene.add_component(component)
    
    assert len(scene.components) == 1
    assert scene.get_component("test_1") == component


def test_scene_graph_remove_component():
    """Test removing a component."""
    scene = SceneGraph()
    
    parent = Component(id="parent", type=ComponentType.SPAR)
    child = Component(id="child", type=ComponentType.RIB, parent_id="parent")
    
    parent.children_ids = ["child"]
    
    scene.add_component(parent)
    scene.add_component(child)
    
    scene.remove_component("child")
    
    assert "child" not in scene.components
    assert "child" not in parent.children_ids


def test_get_components_by_type():
    """Test filtering components by type."""
    scene = SceneGraph()
    
    scene.add_component(Component(id="spar1", type=ComponentType.SPAR))
    scene.add_component(Component(id="spar2", type=ComponentType.SPAR))
    scene.add_component(Component(id="rib1", type=ComponentType.RIB))
    
    spars = scene.get_components_by_type(ComponentType.SPAR)
    assert len(spars) == 2
    
    ribs = scene.get_components_by_type(ComponentType.RIB)
    assert len(ribs) == 1

