"""
Semantic visualization renderer.

Renders drawings with semantic layer coloring and legends.
"""

import logging
from typing import Optional
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# Semantic layer definitions with distinct colors (max 10)
@dataclass
class SemanticLayer:
    """Definition of a semantic layer."""
    
    name: str
    color_bgr: tuple[int, int, int]
    color_rgb: tuple[int, int, int]
    keywords: list[str]
    priority: int = 0


# Define 10 distinct semantic layers for model aircraft
# Keywords include Italian/multilingual terms for international drawings
SEMANTIC_LAYERS = [
    SemanticLayer(
        name="Fuselage Side",
        color_bgr=(0, 0, 200),      # Red
        color_rgb=(200, 0, 0),
        keywords=["fuselage", "fuse", "side", "profile", "f1", "f2", "f3", "f4", "f5", "f6", "f7",
                  "fusoliera", "fianco", "lato"],
        priority=10,
    ),
    SemanticLayer(
        name="Wing Top",
        color_bgr=(200, 100, 0),    # Blue
        color_rgb=(0, 100, 200),
        keywords=["wing", "top", "plan", "planform", "leading", "trailing", "spar",
                  "ala", "piano", "longherone"],
        priority=9,
    ),
    SemanticLayer(
        name="Ribs",
        color_bgr=(0, 200, 0),      # Green
        color_rgb=(0, 200, 0),
        keywords=["rib", "r1", "r2", "r3", "airfoil", "w1", "w2", "w3",
                  "centina", "centine", "nervatura", "profilo"],
        priority=8,
    ),
    SemanticLayer(
        name="Formers",
        color_bgr=(0, 200, 200),    # Yellow
        color_rgb=(200, 200, 0),
        keywords=["former", "bulkhead", "frame", "station", "ordinate",
                  "ordinata", "paratia", "telaio"],
        priority=7,
    ),
    SemanticLayer(
        name="Tail Surfaces",
        color_bgr=(200, 0, 200),    # Magenta
        color_rgb=(200, 0, 200),
        keywords=["tail", "stab", "stabilizer", "fin", "rudder", "elevator", "ts", "hs", "vs",
                  "coda", "deriva", "timone", "equilibratore", "impennaggi"],
        priority=6,
    ),
    SemanticLayer(
        name="Control Surfaces",
        color_bgr=(200, 200, 0),    # Cyan
        color_rgb=(0, 200, 200),
        keywords=["aileron", "flap", "control", "horn", "hinge", "servo",
                  "alettone", "alettoni", "comando", "cerniera"],
        priority=5,
    ),
    SemanticLayer(
        name="Landing Gear",
        color_bgr=(100, 100, 200),  # Light red/pink
        color_rgb=(200, 100, 100),
        keywords=["gear", "wheel", "leg", "strut", "u/c", "uc", "undercarriage", "axle",
                  "carrello", "ruota", "gamba"],
        priority=4,
    ),
    SemanticLayer(
        name="Motor/Engine",
        color_bgr=(50, 150, 255),   # Orange
        color_rgb=(255, 150, 50),
        keywords=["motor", "engine", "prop", "propeller", "cowl", "firewall", "mount",
                  "motore", "elica", "cofano", "supporto"],
        priority=3,
    ),
    SemanticLayer(
        name="Parts/Components",
        color_bgr=(150, 100, 50),   # Brown
        color_rgb=(50, 100, 150),
        keywords=["part", "parts", "component", "piece", "item",
                  "parti", "pezzo", "pezzi", "componente", "n", "i"],
        priority=2,
    ),
    SemanticLayer(
        name="Annotations",
        color_bgr=(100, 50, 50),    # Dark blue
        color_rgb=(50, 50, 100),
        keywords=["text", "label", "dimension", "note", "title", "scale", "dim",
                  "quote", "etichette", "testo", "quota", "scala", "note", "ame_frz"],
        priority=1,
    ),
]

# Color for unclassified elements
UNCLASSIFIED_COLOR_BGR = (180, 180, 180)  # Light gray
UNCLASSIFIED_COLOR_RGB = (180, 180, 180)


class SemanticRenderer:
    """
    Renders drawings with semantic layer coloring.
    
    Assigns colors to detected elements based on semantic classification,
    and produces a visualization with legend.
    """
    
    def __init__(self, layers: Optional[list[SemanticLayer]] = None):
        """
        Initialize semantic renderer.
        
        Args:
            layers: Custom layer definitions (uses defaults if None)
        """
        self.layers = layers or SEMANTIC_LAYERS
    
    def classify_element(
        self,
        element_name: str,
        element_type: str = "",
        layer_name: str = "",
    ) -> Optional[SemanticLayer]:
        """
        Classify an element to a semantic layer.
        
        Args:
            element_name: Name of the element
            element_type: Type of element (line, contour, etc.)
            layer_name: DXF layer name if available
            
        Returns:
            Matching SemanticLayer or None
        """
        # Combine all text for matching
        search_text = f"{element_name} {element_type} {layer_name}".lower()
        
        # Find best matching layer
        best_match = None
        best_priority = -1
        
        for layer in self.layers:
            for keyword in layer.keywords:
                if keyword.lower() in search_text:
                    if layer.priority > best_priority:
                        best_match = layer
                        best_priority = layer.priority
                        break
        
        return best_match
    
    def render_with_layers(
        self,
        image: np.ndarray,
        elements: list[dict],
        show_legend: bool = True,
        legend_position: str = "right",
        background_alpha: float = 0.3,
    ) -> np.ndarray:
        """
        Render image with semantic layer coloring.
        
        Args:
            image: Input image (grayscale or color)
            elements: List of elements with 'name', 'type', 'layer', 'geometry'
            show_legend: Whether to show color legend
            legend_position: "right" or "bottom"
            background_alpha: Opacity of original image (0-1)
            
        Returns:
            Rendered image with colored elements and legend
        """
        # Ensure color image
        if len(image.shape) == 2:
            base_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            base_image = image.copy()
        
        # Create overlay for colored elements
        height, width = base_image.shape[:2]
        overlay = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Track which layers are used
        used_layers: set[str] = set()
        
        # Draw each element with its semantic color
        for element in elements:
            name = element.get("name", "")
            etype = element.get("type", "")
            layer_name = element.get("layer", "")
            geometry = element.get("geometry", {})
            
            # Classify element
            semantic_layer = self.classify_element(name, etype, layer_name)
            
            if semantic_layer:
                color = semantic_layer.color_bgr
                used_layers.add(semantic_layer.name)
            else:
                color = UNCLASSIFIED_COLOR_BGR
                used_layers.add("Unclassified")
            
            # Draw based on geometry type
            self._draw_element(overlay, geometry, color, etype)
        
        # Blend overlay with original
        # Make original image lighter
        faded_base = cv2.addWeighted(
            base_image, background_alpha,
            np.full_like(base_image, 255), 1 - background_alpha,
            0
        )
        
        # Add colored overlay where there's content
        mask = cv2.cvtColor(overlay, cv2.COLOR_BGR2GRAY) > 0
        result = faded_base.copy()
        result[mask] = overlay[mask]
        
        # Add legend if requested
        if show_legend:
            result = self._add_legend(result, used_layers, legend_position)
        
        return result
    
    def render_from_scene_graph(
        self,
        image: np.ndarray,
        scene_graph: "SceneGraph",
        show_legend: bool = True,
    ) -> np.ndarray:
        """
        Render visualization from a scene graph.
        
        Args:
            image: Background image
            scene_graph: Scene graph with components and entities
            show_legend: Whether to show legend
            
        Returns:
            Rendered image
        """
        elements = []
        
        # Add components
        for comp in scene_graph.components:
            elements.append({
                "name": comp.name or comp.component_type.value,
                "type": comp.component_type.value,
                "layer": comp.dxf_layer or "",
                "geometry": {
                    "type": "rect",
                    "x": comp.bounds.x,
                    "y": comp.bounds.y,
                    "width": comp.bounds.width,
                    "height": comp.bounds.height,
                },
            })
        
        # Add entities
        for entity in scene_graph.entities:
            elements.append({
                "name": entity.entity_type,
                "type": entity.entity_type,
                "layer": entity.layer or "",
                "geometry": entity.geometry,
            })
        
        # Add views as outlines
        for view in scene_graph.views:
            elements.append({
                "name": view.name,
                "type": "view",
                "layer": f"VIEW_{view.view_type.value}",
                "geometry": {
                    "type": "rect",
                    "x": view.bounds.x,
                    "y": view.bounds.y,
                    "width": view.bounds.width,
                    "height": view.bounds.height,
                },
            })
        
        return self.render_with_layers(image, elements, show_legend)
    
    def render_from_cv_detections(
        self,
        image: np.ndarray,
        detections: dict,
        dxf_layers: Optional[dict[str, list]] = None,
        show_legend: bool = True,
    ) -> np.ndarray:
        """
        Render visualization from CV detection results.
        
        Args:
            image: Background image
            detections: CV detection results (lines, contours, circles)
            dxf_layers: Optional mapping of layer names to entity indices
            show_legend: Whether to show legend
            
        Returns:
            Rendered image
        """
        elements = []
        
        # Process lines
        for i, line in enumerate(detections.get("lines", [])):
            layer_name = self._get_layer_for_index(dxf_layers, "line", i)
            elements.append({
                "name": f"line_{i}",
                "type": "line",
                "layer": layer_name,
                "geometry": {
                    "type": "line",
                    "start": line.get("start", (0, 0)),
                    "end": line.get("end", (0, 0)),
                },
            })
        
        # Process contours
        for i, contour in enumerate(detections.get("contours", [])):
            layer_name = self._get_layer_for_index(dxf_layers, "contour", i)
            bounds = contour.get("bounds", {})
            elements.append({
                "name": contour.get("shape", f"contour_{i}"),
                "type": "contour",
                "layer": layer_name,
                "geometry": {
                    "type": "rect",
                    "x": bounds.get("x", 0),
                    "y": bounds.get("y", 0),
                    "width": bounds.get("width", 10),
                    "height": bounds.get("height", 10),
                },
            })
        
        # Process circles
        for i, circle in enumerate(detections.get("circles", [])):
            elements.append({
                "name": f"circle_{i}",
                "type": "circle",
                "layer": "",
                "geometry": {
                    "type": "circle",
                    "center": circle.get("center", (0, 0)),
                    "radius": circle.get("radius", 5),
                },
            })
        
        return self.render_with_layers(image, elements, show_legend)
    
    def _draw_element(
        self,
        canvas: np.ndarray,
        geometry: dict,
        color: tuple,
        element_type: str,
    ):
        """Draw an element on the canvas."""
        geom_type = geometry.get("type", element_type)
        
        if geom_type == "line":
            start = geometry.get("start", (0, 0))
            end = geometry.get("end", (0, 0))
            if isinstance(start, dict):
                start = (int(start.get("x", 0)), int(start.get("y", 0)))
            if isinstance(end, dict):
                end = (int(end.get("x", 0)), int(end.get("y", 0)))
            cv2.line(canvas, start, end, color, 2)
        
        elif geom_type == "rect":
            x = int(geometry.get("x", 0))
            y = int(geometry.get("y", 0))
            w = int(geometry.get("width", 10))
            h = int(geometry.get("height", 10))
            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)
        
        elif geom_type == "circle":
            center = geometry.get("center", (0, 0))
            if isinstance(center, dict):
                center = (int(center.get("x", 0)), int(center.get("y", 0)))
            else:
                center = (int(center[0]), int(center[1]))
            radius = int(geometry.get("radius", 5))
            cv2.circle(canvas, center, radius, color, 2)
        
        elif geom_type == "polyline":
            points = geometry.get("points", [])
            if len(points) >= 2:
                pts = []
                for p in points:
                    if isinstance(p, dict):
                        pts.append([int(p.get("x", 0)), int(p.get("y", 0))])
                    else:
                        pts.append([int(p[0]), int(p[1])])
                pts = np.array(pts, dtype=np.int32)
                cv2.polylines(canvas, [pts], geometry.get("closed", False), color, 2)
    
    def _add_legend(
        self,
        image: np.ndarray,
        used_layers: set[str],
        position: str,
    ) -> np.ndarray:
        """Add color legend to image."""
        # Legend dimensions
        legend_width = 200
        legend_item_height = 25
        legend_padding = 10
        
        # Filter to only used layers
        legend_items = []
        for layer in self.layers:
            if layer.name in used_layers:
                legend_items.append((layer.name, layer.color_bgr))
        
        if "Unclassified" in used_layers:
            legend_items.append(("Unclassified", UNCLASSIFIED_COLOR_BGR))
        
        legend_height = len(legend_items) * legend_item_height + legend_padding * 2 + 30
        
        if position == "right":
            # Add legend to the right
            result = np.full(
                (image.shape[0], image.shape[1] + legend_width, 3),
                255,
                dtype=np.uint8,
            )
            result[:, :image.shape[1]] = image
            legend_x = image.shape[1] + legend_padding
            legend_y = legend_padding
        else:
            # Add legend to the bottom
            result = np.full(
                (image.shape[0] + legend_height, image.shape[1], 3),
                255,
                dtype=np.uint8,
            )
            result[:image.shape[0], :] = image
            legend_x = legend_padding
            legend_y = image.shape[0] + legend_padding
        
        # Draw legend title
        cv2.putText(
            result,
            "LAYER LEGEND",
            (legend_x, legend_y + 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
        )
        
        # Draw legend items
        for i, (name, color) in enumerate(legend_items):
            y = legend_y + 30 + i * legend_item_height
            
            # Color box
            cv2.rectangle(
                result,
                (legend_x, y),
                (legend_x + 20, y + 15),
                color,
                -1,
            )
            cv2.rectangle(
                result,
                (legend_x, y),
                (legend_x + 20, y + 15),
                (0, 0, 0),
                1,
            )
            
            # Label
            cv2.putText(
                result,
                name[:20],  # Truncate long names
                (legend_x + 25, y + 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 0),
                1,
            )
        
        return result
    
    def _get_layer_for_index(
        self,
        dxf_layers: Optional[dict],
        element_type: str,
        index: int,
    ) -> str:
        """Get DXF layer name for an element index."""
        if not dxf_layers:
            return ""
        
        for layer_name, indices in dxf_layers.items():
            if index in indices:
                return layer_name
        
        return ""


def create_semantic_visualization(
    image: np.ndarray,
    detections: dict,
    scene_graph: Optional["SceneGraph"] = None,
    show_legend: bool = True,
) -> np.ndarray:
    """
    Convenience function to create semantic visualization.
    
    Args:
        image: Input image
        detections: CV detection results
        scene_graph: Optional scene graph
        show_legend: Whether to show legend
        
    Returns:
        Rendered visualization
    """
    renderer = SemanticRenderer()
    
    if scene_graph:
        return renderer.render_from_scene_graph(image, scene_graph, show_legend)
    else:
        return renderer.render_from_cv_detections(image, detections, show_legend=show_legend)

