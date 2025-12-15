"""
Geometry modification utilities.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GeometryModifier:
    """
    Utilities for modifying DXF geometry.
    """
    
    def scale_entity(
        self,
        entity: Any,
        scale_x: float,
        scale_y: float,
        center: Optional[tuple] = None,
    ):
        """
        Scale a DXF entity.
        
        Args:
            entity: ezdxf entity
            scale_x: X scale factor
            scale_y: Y scale factor
            center: Center point for scaling (defaults to entity center)
        """
        # Get entity bounds for center calculation
        if center is None:
            # Would need to calculate entity center
            center = (0, 0)
        
        # Apply transformation
        # This would use ezdxf's transformation capabilities
        logger.debug(f"Scaling entity by ({scale_x}, {scale_y}) around {center}")
    
    def translate_entity(
        self,
        entity: Any,
        dx: float,
        dy: float,
    ):
        """
        Translate a DXF entity.
        
        Args:
            entity: ezdxf entity
            dx: X translation
            dy: Y translation
        """
        logger.debug(f"Translating entity by ({dx}, {dy})")
    
    def replace_cross_section(
        self,
        entity: Any,
        old_width: float,
        old_height: float,
        new_width: float,
        new_height: float,
    ):
        """
        Replace cross-section dimensions.
        
        For spar/stringer elements, this modifies the visual representation.
        
        Args:
            entity: ezdxf entity
            old_width: Original width
            old_height: Original height
            new_width: New width
            new_height: New height
        """
        scale_x = new_width / old_width if old_width > 0 else 1
        scale_y = new_height / old_height if old_height > 0 else 1
        
        self.scale_entity(entity, scale_x, scale_y)
    
    def update_notch(
        self,
        rib_entity: Any,
        notch_position: float,
        old_size: tuple,
        new_size: tuple,
    ):
        """
        Update spar notch in a rib.
        
        When spar size changes, the notches in ribs need to be updated.
        
        Args:
            rib_entity: Rib polyline entity
            notch_position: Position of notch along rib
            old_size: Old notch size (width, height)
            new_size: New notch size (width, height)
        """
        logger.debug(f"Updating notch at {notch_position}: {old_size} → {new_size}")
        # Would need to modify polyline vertices


