"""Export scene graph to DXF format."""

from pathlib import Path
from typing import Dict, List, Optional

import ezdxf
from ezdxf import colors

from ..geometry.projection import OrthographicProjector
from ..scene.scene_graph import SceneGraph


class DXFExporter:
    """Export scene graph to DXF file."""

    def __init__(self):
        """Initialize exporter."""
        self.projector = OrthographicProjector()

    def export(
        self,
        scene: SceneGraph,
        output_path: str | Path,
        views: Optional[List[str]] = None,
    ):
        """
        Export scene graph to DXF file.
        
        Args:
            scene: Scene graph to export
            output_path: Path to output DXF file
            views: List of views to include (default: all)
        """
        if views is None:
            views = ["front", "top", "side"]
        
        # Create new DXF document
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        
        # Create layers for different views
        for view in views:
            doc.layers.new(f"VIEW_{view.upper()}", dxfattribs={"color": colors.BLUE})
        
        # Project scene to views
        projected_views = self.projector.project_to_views(scene)
        
        # Add entities to DXF
        view_offsets = {
            "front": (0, 0),
            "top": (0, 10),  # Offset top view
            "side": (15, 0),  # Offset side view
        }
        
        for view_name in views:
            if view_name not in projected_views:
                continue
            
            offset_x, offset_y = view_offsets.get(view_name, (0, 0))
            layer_name = f"VIEW_{view_name.upper()}"
            
            for entity_data in projected_views[view_name]:
                self._add_entity(msp, entity_data, layer_name, offset_x, offset_y)
        
        # Save DXF
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(output_path))

    def _add_entity(self, msp, entity_data: Dict, layer: str, offset_x: float, offset_y: float):
        """Add an entity to modelspace with offset."""
        entity_type = entity_data.get("type")
        
        if entity_type == "LINE":
            start = entity_data["start"]
            end = entity_data["end"]
            msp.add_line(
                (start[0] + offset_x, start[1] + offset_y),
                (end[0] + offset_x, end[1] + offset_y),
                dxfattribs={"layer": layer},
            )
        
        elif entity_type == "RECTANGLE":
            min_pt = entity_data["min"]
            max_pt = entity_data["max"]
            # Create rectangle as polyline
            points = [
                (min_pt[0] + offset_x, min_pt[1] + offset_y),
                (max_pt[0] + offset_x, min_pt[1] + offset_y),
                (max_pt[0] + offset_x, max_pt[1] + offset_y),
                (min_pt[0] + offset_x, max_pt[1] + offset_y),
            ]
            msp.add_lwpolyline(
                points, close=True, dxfattribs={"layer": layer}
            )

