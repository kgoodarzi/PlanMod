"""
DXF block management.
"""

import logging
from typing import Any

from backend.shared.models import Component, ComponentType

logger = logging.getLogger(__name__)


class BlockManager:
    """
    Manages DXF blocks for reusable components.
    """
    
    def create_component_block(
        self,
        doc: Any,
        block_name: str,
        component: Component,
    ):
        """
        Create a block definition for a component.
        
        Args:
            doc: DXF document
            block_name: Name for the block
            component: Component to create block for
        """
        # Check if block already exists
        if block_name in doc.blocks:
            return
        
        try:
            block = doc.blocks.new(name=block_name)
            
            # Draw component geometry based on type
            self._draw_component_geometry(block, component)
            
            logger.debug(f"Created block: {block_name}")
            
        except Exception as e:
            logger.warning(f"Failed to create block {block_name}: {e}")
    
    def _draw_component_geometry(self, block: Any, component: Component):
        """Draw geometry for a component block."""
        # Get dimensions
        width = component.bounds.width
        height = component.bounds.height
        
        # Draw based on component type
        if component.component_type == ComponentType.RIB:
            self._draw_rib(block, width, height)
        elif component.component_type == ComponentType.FORMER:
            self._draw_former(block, width, height)
        elif component.component_type == ComponentType.SPAR:
            self._draw_spar(block, width, height)
        elif component.component_type in (ComponentType.FASTENER, ComponentType.HINGE):
            self._draw_fastener(block, width, height)
        else:
            # Default: simple rectangle
            self._draw_rectangle(block, width, height)
    
    def _draw_rectangle(self, block: Any, width: float, height: float):
        """Draw a simple rectangle."""
        points = [
            (0, 0),
            (width, 0),
            (width, height),
            (0, height),
            (0, 0),
        ]
        block.add_lwpolyline(points)
    
    def _draw_rib(self, block: Any, width: float, height: float):
        """Draw an airfoil-like rib shape."""
        # Simple airfoil approximation
        import math
        
        num_points = 20
        points = []
        
        # Upper surface
        for i in range(num_points):
            x = width * i / (num_points - 1)
            # NACA-like thickness distribution
            t = 0.3 * height  # Max thickness
            y_upper = t * (1 - (2 * x / width - 1) ** 2)
            points.append((x, height / 2 + y_upper))
        
        # Lower surface (reversed)
        for i in range(num_points - 1, -1, -1):
            x = width * i / (num_points - 1)
            t = 0.3 * height
            y_lower = t * (1 - (2 * x / width - 1) ** 2) * 0.5
            points.append((x, height / 2 - y_lower))
        
        points.append(points[0])  # Close the shape
        
        block.add_lwpolyline(points)
        
        # Add spar notches (simplified)
        spar_pos = width * 0.25
        notch_size = height * 0.1
        block.add_line((spar_pos, height / 2 - notch_size), (spar_pos, height / 2 + notch_size))
    
    def _draw_former(self, block: Any, width: float, height: float):
        """Draw a former (fuselage cross-section)."""
        # Oval/ellipse shape
        import math
        
        num_points = 24
        points = []
        
        cx, cy = width / 2, height / 2
        rx, ry = width / 2, height / 2
        
        for i in range(num_points + 1):
            angle = 2 * math.pi * i / num_points
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            points.append((x, y))
        
        block.add_lwpolyline(points)
        
        # Add center cross
        block.add_line((cx - width * 0.1, cy), (cx + width * 0.1, cy))
        block.add_line((cx, cy - height * 0.1), (cx, cy + height * 0.1))
    
    def _draw_spar(self, block: Any, width: float, height: float):
        """Draw a spar (rectangular beam cross-section)."""
        # Simple rectangle with indication of grain direction
        self._draw_rectangle(block, width, height)
        
        # Add grain direction lines
        num_lines = 3
        for i in range(1, num_lines + 1):
            x = width * i / (num_lines + 1)
            block.add_line((x, 0), (x, height))
    
    def _draw_fastener(self, block: Any, width: float, height: float):
        """Draw a fastener symbol."""
        import math
        
        # Circle for fastener
        radius = min(width, height) / 2
        center = (width / 2, height / 2)
        
        block.add_circle(center, radius)
        
        # Cross inside
        block.add_line(
            (center[0] - radius * 0.5, center[1]),
            (center[0] + radius * 0.5, center[1]),
        )
        block.add_line(
            (center[0], center[1] - radius * 0.5),
            (center[0], center[1] + radius * 0.5),
        )


