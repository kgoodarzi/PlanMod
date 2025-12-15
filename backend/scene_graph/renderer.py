"""
Scene graph visualization renderer.
"""

import logging
from typing import Optional

import numpy as np

from backend.shared.models import SceneGraph, ViewType

logger = logging.getLogger(__name__)


# Color palette for different element types
VIEW_COLORS = {
    ViewType.TOP: (255, 100, 100),      # Red
    ViewType.SIDE: (100, 255, 100),     # Green
    ViewType.FRONT: (100, 100, 255),    # Blue
    ViewType.SECTION: (255, 255, 100),  # Yellow
    ViewType.DETAIL: (255, 100, 255),   # Magenta
    ViewType.UNKNOWN: (150, 150, 150),  # Gray
}


class SceneGraphRenderer:
    """
    Renders scene graph as visualization image.
    """
    
    def __init__(
        self,
        background_color: tuple = (255, 255, 255),
        line_thickness: int = 2,
        font_scale: float = 0.5,
    ):
        self.background_color = background_color
        self.line_thickness = line_thickness
        self.font_scale = font_scale
    
    def render(
        self,
        scene_graph: SceneGraph,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> np.ndarray:
        """
        Render scene graph as image.
        
        Args:
            scene_graph: Scene graph to render
            width: Output width (default: scene_graph.image_width)
            height: Output height (default: scene_graph.image_height)
            
        Returns:
            Rendered image as numpy array
        """
        import cv2
        
        width = width or scene_graph.image_width or 1920
        height = height or scene_graph.image_height or 1080
        
        # Create canvas
        canvas = np.full((height, width, 3), self.background_color, dtype=np.uint8)
        
        # Draw views
        for view in scene_graph.views:
            color = VIEW_COLORS.get(view.view_type, VIEW_COLORS[ViewType.UNKNOWN])
            
            x1 = int(view.bounds.x)
            y1 = int(view.bounds.y)
            x2 = int(view.bounds.x + view.bounds.width)
            y2 = int(view.bounds.y + view.bounds.height)
            
            # Draw rectangle
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, self.line_thickness)
            
            # Draw label
            label = f"{view.name} ({view.view_type.value})"
            cv2.putText(
                canvas,
                label,
                (x1 + 5, y1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.font_scale,
                color,
                1,
            )
        
        # Draw components
        for component in scene_graph.components:
            x1 = int(component.bounds.x)
            y1 = int(component.bounds.y)
            x2 = int(component.bounds.x + component.bounds.width)
            y2 = int(component.bounds.y + component.bounds.height)
            
            # Draw with transparency effect using dashed lines
            color = (0, 128, 255)  # Orange for components
            
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 1)
            
            # Draw component type label
            if component.name:
                cv2.putText(
                    canvas,
                    component.name[:15],
                    (x1 + 2, y1 + 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    color,
                    1,
                )
        
        # Draw annotations
        for annotation in scene_graph.annotations:
            cx, cy = annotation.bounds.center
            
            cv2.circle(canvas, (int(cx), int(cy)), 3, (0, 0, 0), -1)
            
            cv2.putText(
                canvas,
                annotation.text[:20],
                (int(cx) + 5, int(cy)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.3,
                (0, 0, 0),
                1,
            )
        
        # Add legend
        self._draw_legend(canvas, width, height)
        
        return canvas
    
    def _draw_legend(self, canvas: np.ndarray, width: int, height: int):
        """Draw legend on canvas."""
        import cv2
        
        legend_x = width - 200
        legend_y = 20
        
        cv2.putText(
            canvas,
            "Legend:",
            (legend_x, legend_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
        )
        
        for i, (view_type, color) in enumerate(VIEW_COLORS.items()):
            y = legend_y + 20 + i * 18
            
            cv2.rectangle(
                canvas,
                (legend_x, y - 10),
                (legend_x + 15, y + 2),
                color,
                -1,
            )
            
            cv2.putText(
                canvas,
                view_type.value,
                (legend_x + 20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 0),
                1,
            )
    
    def render_component_list(self, scene_graph: SceneGraph) -> str:
        """
        Render scene graph as text list.
        
        Args:
            scene_graph: Scene graph to render
            
        Returns:
            Formatted text representation
        """
        lines = [
            f"# Scene Graph: {scene_graph.title or 'Untitled'}",
            f"ID: {scene_graph.id}",
            f"Source: {scene_graph.source_file or 'Unknown'}",
            "",
            "## Views",
        ]
        
        for view in scene_graph.views:
            lines.append(f"- **{view.name}** ({view.view_type.value})")
            lines.append(f"  - Bounds: {view.bounds.x:.0f}, {view.bounds.y:.0f}, "
                        f"{view.bounds.width:.0f}x{view.bounds.height:.0f}")
            lines.append(f"  - Confidence: {view.classification_confidence:.2f}")
            lines.append(f"  - Components: {len(view.component_ids)}")
        
        lines.extend(["", "## Components"])
        
        for comp in scene_graph.components:
            lines.append(f"- **{comp.name or comp.id[:8]}** ({comp.component_type.value})")
            if comp.attributes.material:
                lines.append(f"  - Material: {comp.attributes.material.value}")
            lines.append(f"  - Confidence: {comp.classification_confidence:.2f}")
            if comp.dxf_layer:
                lines.append(f"  - DXF Layer: {comp.dxf_layer}")
        
        if scene_graph.annotations:
            lines.extend(["", "## Annotations"])
            for ann in scene_graph.annotations[:20]:  # Limit to 20
                lines.append(f"- {ann.text} ({ann.annotation_type})")
        
        if scene_graph.uncertainties:
            lines.extend(["", "## Uncertainties (Need Human Review)"])
            for unc in scene_graph.uncertainties:
                lines.append(f"- ⚠️ {unc}")
        
        return "\n".join(lines)


