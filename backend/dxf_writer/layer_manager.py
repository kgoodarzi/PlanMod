"""
DXF layer management.
"""

from typing import Any

from backend.shared.models import ViewType, ComponentType


# DXF color indices
class DXFColors:
    RED = 1
    YELLOW = 2
    GREEN = 3
    CYAN = 4
    BLUE = 5
    MAGENTA = 6
    WHITE = 7
    GRAY = 8
    LIGHT_GRAY = 9


class LayerManager:
    """
    Manages DXF layers for the drawing.
    """
    
    # Standard layers
    STANDARD_LAYERS = {
        "0": DXFColors.WHITE,
        "DEFPOINTS": DXFColors.WHITE,
        "ANNOTATIONS": DXFColors.CYAN,
        "DIMENSIONS": DXFColors.GREEN,
        "CONSTRUCTION": DXFColors.GRAY,
        "CENTERLINES": DXFColors.MAGENTA,
    }
    
    # View type colors
    VIEW_COLORS = {
        ViewType.TOP: DXFColors.RED,
        ViewType.SIDE: DXFColors.GREEN,
        ViewType.FRONT: DXFColors.BLUE,
        ViewType.REAR: DXFColors.CYAN,
        ViewType.SECTION: DXFColors.YELLOW,
        ViewType.DETAIL: DXFColors.MAGENTA,
        ViewType.ISOMETRIC: DXFColors.WHITE,
        ViewType.UNKNOWN: DXFColors.GRAY,
    }
    
    # Component type colors
    COMPONENT_COLORS = {
        ComponentType.RIB: DXFColors.RED,
        ComponentType.FORMER: DXFColors.BLUE,
        ComponentType.BULKHEAD: DXFColors.CYAN,
        ComponentType.SPAR: DXFColors.GREEN,
        ComponentType.STRINGER: DXFColors.YELLOW,
        ComponentType.LONGERON: DXFColors.YELLOW,
        ComponentType.SKIN: DXFColors.LIGHT_GRAY,
        ComponentType.COVERING: DXFColors.LIGHT_GRAY,
        ComponentType.AILERON: DXFColors.MAGENTA,
        ComponentType.ELEVATOR: DXFColors.MAGENTA,
        ComponentType.RUDDER: DXFColors.MAGENTA,
        ComponentType.FLAP: DXFColors.MAGENTA,
        ComponentType.FASTENER: DXFColors.WHITE,
        ComponentType.HINGE: DXFColors.WHITE,
        ComponentType.BRACKET: DXFColors.CYAN,
        ComponentType.MOUNT: DXFColors.CYAN,
        ComponentType.MOTOR: DXFColors.RED,
        ComponentType.PROPELLER: DXFColors.GREEN,
        ComponentType.ENGINE: DXFColors.RED,
        ComponentType.WHEEL: DXFColors.GRAY,
        ComponentType.STRUT: DXFColors.GRAY,
        ComponentType.SKID: DXFColors.GRAY,
        ComponentType.BALSA_SHEET: DXFColors.YELLOW,
        ComponentType.BALSA_STICK: DXFColors.YELLOW,
        ComponentType.PLYWOOD: DXFColors.BLUE,
        ComponentType.CARBON_FIBER: DXFColors.CYAN,
        ComponentType.CUSTOM: DXFColors.WHITE,
        ComponentType.UNKNOWN: DXFColors.GRAY,
    }
    
    def create_standard_layers(self, doc: Any):
        """Create standard layers in the document."""
        for layer_name, color in self.STANDARD_LAYERS.items():
            if layer_name not in doc.layers:
                doc.layers.add(layer_name, color=color)
    
    def create_layer(
        self,
        doc: Any,
        name: str,
        color: int = DXFColors.WHITE,
        linetype: str = "CONTINUOUS",
    ):
        """Create a layer in the document."""
        if name not in doc.layers:
            doc.layers.add(
                name,
                color=color,
                linetype=linetype,
            )
    
    def get_view_color(self, view_type: ViewType) -> int:
        """Get color for a view type."""
        return self.VIEW_COLORS.get(view_type, DXFColors.WHITE)
    
    def get_component_color(self, component_type: ComponentType) -> int:
        """Get color for a component type."""
        return self.COMPONENT_COLORS.get(component_type, DXFColors.WHITE)


