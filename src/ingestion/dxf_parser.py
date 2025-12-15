"""DXF file parsing and rendering to raster images for VLM processing."""

import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ezdxf
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

matplotlib.use("Agg")  # Non-interactive backend


class DXFParser:
    """Parse DXF files and render to PNG images for VLM analysis."""

    def __init__(self, dxf_path: str | Path):
        """Initialize parser with DXF file path."""
        self.dxf_path = Path(dxf_path)
        if not self.dxf_path.exists():
            raise FileNotFoundError(f"DXF file not found: {dxf_path}")
        
        self.doc = ezdxf.readfile(str(self.dxf_path))
        self.modelspace = self.doc.modelspace()
        self._bounds = None

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get bounding box of all entities in modelspace."""
        if self._bounds is not None:
            return self._bounds
        
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")
        
        for entity in self.modelspace:
            if hasattr(entity, "bbox"):
                bbox = entity.bbox()
                if bbox:
                    min_x = min(min_x, bbox.extmin.x)
                    min_y = min(min_y, bbox.extmin.y)
                    max_x = max(max_x, bbox.extmax.x)
                    max_y = max(max_y, bbox.extmax.y)
        
        # Add padding
        padding = max((max_x - min_x), (max_y - min_y)) * 0.1
        self._bounds = (
            min_x - padding,
            min_y - padding,
            max_x + padding,
            max_y + padding,
        )
        
        return self._bounds

    def render_to_image(
        self,
        width: int = 2048,
        height: int = 2048,
        dpi: int = 150,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> Image.Image:
        """
        Render DXF to PNG image.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            dpi: Resolution for rendering
            bounds: Optional bounding box (min_x, min_y, max_x, max_y)
        
        Returns:
            PIL Image object
        """
        if bounds is None:
            bounds = self.get_bounds()
        
        min_x, min_y, max_x, max_y = bounds
        fig_width = (max_x - min_x) / dpi * 12
        fig_height = (max_y - min_y) / dpi * 12
        
        # Maintain aspect ratio
        aspect = fig_height / fig_width
        if aspect > height / width:
            fig_width = fig_height / aspect
        else:
            fig_height = fig_width * aspect
        
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
        ax.set_xlim(min_x, max_x)
        ax.set_ylim(min_y, max_y)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.invert_yaxis()  # DXF Y-axis is typically inverted
        
        # Render entities
        for entity in self.modelspace:
            self._render_entity(ax, entity)
        
        # Convert to PIL Image
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, dpi=dpi)
        buf.seek(0)
        img = Image.open(buf)
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        plt.close(fig)
        
        return img

    def _render_entity(self, ax, entity):
        """Render a single DXF entity to matplotlib axes."""
        entity_type = entity.dxftype()
        
        if entity_type == "LINE":
            ax.plot([entity.dxf.start.x, entity.dxf.end.x], 
                   [entity.dxf.start.y, entity.dxf.end.y], 
                   "k-", linewidth=0.5)
        
        elif entity_type == "POLYLINE" or entity_type == "LWPOLYLINE":
            points = list(entity.vertices())
            if points:
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                if entity.is_closed:
                    x_coords.append(x_coords[0])
                    y_coords.append(y_coords[0])
                ax.plot(x_coords, y_coords, "k-", linewidth=0.5)
        
        elif entity_type == "CIRCLE":
            circle = plt.Circle(
                (entity.dxf.center.x, entity.dxf.center.y),
                entity.dxf.radius,
                fill=False,
                color="k",
                linewidth=0.5,
            )
            ax.add_patch(circle)
        
        elif entity_type == "ARC":
            from matplotlib.patches import Arc
            arc = Arc(
                (entity.dxf.center.x, entity.dxf.center.y),
                2 * entity.dxf.radius,
                2 * entity.dxf.radius,
                angle=0,
                theta1=np.degrees(entity.dxf.start_angle),
                theta2=np.degrees(entity.dxf.end_angle),
                color="k",
                linewidth=0.5,
            )
            ax.add_patch(arc)
        
        elif entity_type == "TEXT" or entity_type == "MTEXT":
            if entity_type == "TEXT":
                pos = (entity.dxf.insert.x, entity.dxf.insert.y)
                text = entity.dxf.text
            else:
                pos = (entity.dxf.insert.x, entity.dxf.insert.y)
                text = entity.text
            ax.text(pos[0], pos[1], text, fontsize=6, ha="left", va="bottom")

    def render_views(
        self, output_dir: Optional[Path] = None
    ) -> Dict[str, Image.Image]:
        """
        Render all views (front, top, side) from DXF.
        
        For MVP, assumes the entire drawing contains all views.
        Later, this will use VLM to identify view regions.
        
        Args:
            output_dir: Optional directory to save rendered images
        
        Returns:
            Dictionary mapping view names to PIL Images
        """
        # For MVP, render the entire drawing
        # In future, this will crop to specific view regions
        full_image = self.render_to_image()
        
        images = {"full": full_image}
        
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            full_image.save(output_dir / "full.png")
        
        return images

    def get_entities(self) -> List:
        """Get all entities from modelspace."""
        return list(self.modelspace)

    def get_layers(self) -> List[str]:
        """Get list of layer names in the DXF."""
        return [layer.dxf.name for layer in self.doc.layers]

