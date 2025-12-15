"""
DXF file writer using ezdxf.
"""

import io
import logging
from typing import Any, Optional

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment

from backend.shared.models import SceneGraph, ViewType, ComponentType
from backend.dxf_writer.layer_manager import LayerManager
from backend.dxf_writer.block_manager import BlockManager

logger = logging.getLogger(__name__)


class DXFWriter:
    """
    Writes DXF files from scene graphs using ezdxf.
    """
    
    def __init__(
        self,
        dxf_version: str = "R2018",
        units_type: int = units.MM,
    ):
        self.dxf_version = dxf_version
        self.units_type = units_type
        
        self.layer_manager = LayerManager()
        self.block_manager = BlockManager()
    
    def write(self, scene_graph: SceneGraph) -> bytes:
        """
        Write scene graph to DXF format.
        
        Args:
            scene_graph: Scene graph to convert
            
        Returns:
            DXF file as bytes
        """
        logger.info(f"Writing DXF for scene graph {scene_graph.id}")
        
        # Create new DXF document
        doc = ezdxf.new(self.dxf_version)
        doc.units = self.units_type
        
        msp = doc.modelspace()
        
        # Set up layers
        self._setup_layers(doc, scene_graph)
        
        # Set up blocks for components
        self._setup_blocks(doc, scene_graph)
        
        # Write views
        for view in scene_graph.views:
            self._write_view(msp, view, scene_graph)
        
        # Write components
        for component in scene_graph.components:
            self._write_component(msp, component, scene_graph)
        
        # Write geometry entities
        for entity in scene_graph.entities:
            self._write_entity(msp, entity)
        
        # Write annotations
        for annotation in scene_graph.annotations:
            self._write_annotation(msp, annotation)
        
        # Add metadata
        self._add_metadata(doc, scene_graph)
        
        # Write to string stream then encode to bytes
        stream = io.StringIO()
        doc.write(stream)
        stream.seek(0)
        
        return stream.read().encode('utf-8')
    
    def _setup_layers(self, doc: Any, scene_graph: SceneGraph):
        """Set up DXF layers."""
        # Standard layers
        self.layer_manager.create_standard_layers(doc)
        
        # View layers
        for view in scene_graph.views:
            layer_name = f"VIEW_{view.view_type.value.upper()}"
            color = self.layer_manager.get_view_color(view.view_type)
            self.layer_manager.create_layer(doc, layer_name, color)
        
        # Component layers
        component_types = set(c.component_type for c in scene_graph.components)
        for comp_type in component_types:
            layer_name = f"COMP_{comp_type.value.upper()}"
            color = self.layer_manager.get_component_color(comp_type)
            self.layer_manager.create_layer(doc, layer_name, color)
    
    def _setup_blocks(self, doc: Any, scene_graph: SceneGraph):
        """Set up DXF blocks for reusable components."""
        for component in scene_graph.components:
            if component.dxf_block_name:
                self.block_manager.create_component_block(
                    doc,
                    component.dxf_block_name,
                    component,
                )
    
    def _write_view(self, msp: Any, view: Any, scene_graph: SceneGraph):
        """Write a view to the modelspace."""
        layer_name = f"VIEW_{view.view_type.value.upper()}"
        
        # Draw view boundary
        points = [
            (view.bounds.x, view.bounds.y),
            (view.bounds.x + view.bounds.width, view.bounds.y),
            (view.bounds.x + view.bounds.width, view.bounds.y + view.bounds.height),
            (view.bounds.x, view.bounds.y + view.bounds.height),
            (view.bounds.x, view.bounds.y),
        ]
        
        msp.add_lwpolyline(
            points,
            dxfattribs={"layer": layer_name},
        )
        
        # Add view label
        msp.add_text(
            view.name or f"{view.view_type.value} view",
            dxfattribs={
                "layer": layer_name,
                "height": 5,
            },
        ).set_placement(
            (view.bounds.x + 5, view.bounds.y + view.bounds.height - 10),
            align=TextEntityAlignment.LEFT,
        )
    
    def _write_component(self, msp: Any, component: Any, scene_graph: SceneGraph):
        """Write a component to the modelspace."""
        layer_name = component.dxf_layer or f"COMP_{component.component_type.value.upper()}"
        
        # If block exists, insert it
        if component.dxf_block_name:
            try:
                msp.add_blockref(
                    component.dxf_block_name,
                    (component.bounds.x, component.bounds.y),
                    dxfattribs={"layer": layer_name},
                )
            except Exception:
                # Block doesn't exist, draw bounding box instead
                self._draw_component_bounds(msp, component, layer_name)
        else:
            self._draw_component_bounds(msp, component, layer_name)
    
    def _draw_component_bounds(self, msp: Any, component: Any, layer_name: str):
        """Draw component bounding box."""
        points = [
            (component.bounds.x, component.bounds.y),
            (component.bounds.x + component.bounds.width, component.bounds.y),
            (component.bounds.x + component.bounds.width, component.bounds.y + component.bounds.height),
            (component.bounds.x, component.bounds.y + component.bounds.height),
            (component.bounds.x, component.bounds.y),
        ]
        
        msp.add_lwpolyline(
            points,
            dxfattribs={"layer": layer_name},
        )
        
        # Add component ID
        if component.name:
            msp.add_text(
                component.name,
                dxfattribs={
                    "layer": layer_name,
                    "height": 2,
                },
            ).set_placement(
                (component.bounds.x + 2, component.bounds.y + 2),
                align=TextEntityAlignment.LEFT,
            )
    
    def _write_entity(self, msp: Any, entity: Any):
        """Write a geometry entity to the modelspace."""
        layer = entity.layer or "0"
        geom = entity.geometry
        
        # Skip entities that don't have proper geometry data
        if not geom or "dxf_type" in geom:
            # This is a placeholder entity from DXF import, skip it
            return
        
        try:
            if entity.entity_type == "line":
                start = geom.get("start", {})
                end = geom.get("end", {})
                if isinstance(start, dict) and isinstance(end, dict):
                    msp.add_line(
                        (start.get("x", 0), start.get("y", 0)),
                        (end.get("x", 0), end.get("y", 0)),
                        dxfattribs={"layer": layer},
                    )
            
            elif entity.entity_type == "polyline":
                points = geom.get("points", [])
                if points:
                    converted_points = []
                    for p in points:
                        if isinstance(p, dict):
                            converted_points.append((p.get("x", 0), p.get("y", 0)))
                        elif isinstance(p, (list, tuple)):
                            converted_points.append(tuple(p[:2]))
                    if converted_points:
                        msp.add_lwpolyline(
                            converted_points,
                            close=geom.get("closed", False),
                            dxfattribs={"layer": layer},
                        )
            
            elif entity.entity_type == "circle":
                center = geom.get("center", (0, 0))
                if isinstance(center, dict):
                    center = (center.get("x", 0), center.get("y", 0))
                elif isinstance(center, (list, tuple)):
                    center = tuple(center[:2])
                
                radius = geom.get("radius", 1)
                if radius > 0:
                    msp.add_circle(
                        center,
                        radius,
                        dxfattribs={"layer": layer},
                    )
            
            elif entity.entity_type == "arc":
                center = geom.get("center", (0, 0))
                if isinstance(center, dict):
                    center = (center.get("x", 0), center.get("y", 0))
                elif isinstance(center, (list, tuple)):
                    center = tuple(center[:2])
                
                radius = geom.get("radius", 1)
                if radius > 0:
                    msp.add_arc(
                        center,
                        radius,
                        geom.get("start_angle", 0),
                        geom.get("end_angle", 360),
                        dxfattribs={"layer": layer},
                    )
        except Exception as e:
            # Log but don't fail on individual entity errors
            pass
    
    def _write_annotation(self, msp: Any, annotation: Any):
        """Write an annotation to the modelspace."""
        layer = "ANNOTATIONS"
        
        msp.add_text(
            annotation.text,
            dxfattribs={
                "layer": layer,
                "height": 3,
            },
        ).set_placement(
            (annotation.bounds.x, annotation.bounds.y),
            align=TextEntityAlignment.LEFT,
        )
    
    def _add_metadata(self, doc: Any, scene_graph: SceneGraph):
        """Add metadata to DXF document."""
        # Set document properties
        doc.header["$INSUNITS"] = self.units_type
        
        # Add custom data
        if scene_graph.title:
            doc.header["$PROJECTNAME"] = scene_graph.title[:255]

