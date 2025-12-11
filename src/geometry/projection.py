"""Orthographic projection from 3D scene graph to 2D DXF."""

from typing import Dict, List, Tuple

import ezdxf
from ezdxf.math import Vec3

from ..scene.scene_graph import Component, SceneGraph


class OrthographicProjector:
    """Project 3D scene graph to 2D orthographic views."""

    def project_to_views(self, scene: SceneGraph) -> Dict[str, List]:
        """
        Project scene graph to front, top, and side views.
        
        Returns:
            Dictionary mapping view names to lists of 2D entities
        """
        views = {
            "front": self._project_front_view(scene),
            "top": self._project_top_view(scene),
            "side": self._project_side_view(scene),
        }
        return views

    def _project_front_view(self, scene: SceneGraph) -> List[Dict]:
        """Project to front view (X-Y plane, Z=0)."""
        entities = []
        
        for component in scene.components.values():
            # Project component to front view
            proj_entities = self._project_component(component, "front")
            entities.extend(proj_entities)
        
        return entities

    def _project_top_view(self, scene: SceneGraph) -> List[Dict]:
        """Project to top view (X-Z plane, Y=0)."""
        entities = []
        
        for component in scene.components.values():
            proj_entities = self._project_component(component, "top")
            entities.extend(proj_entities)
        
        return entities

    def _project_side_view(self, scene: SceneGraph) -> List[Dict]:
        """Project to side view (Y-Z plane, X=0)."""
        entities = []
        
        for component in scene.components.values():
            proj_entities = self._project_component(component, "side")
            entities.extend(proj_entities)
        
        return entities

    def _project_component(self, component: Component, view: str) -> List[Dict]:
        """
        Project a single component to a view.
        
        Returns:
            List of entity dictionaries with type and coordinates
        """
        entities = []
        dims = component.dimensions
        pos = component.position
        
        comp_type = component.type
        
        if comp_type in ["stick", "spar", "longeron", "stringer"]:
            # Linear component: project as line
            length = dims.get("length", 1.0)
            width = dims.get("width", 0.125)
            height = dims.get("height", 0.125)
            
            if view == "front":
                # Front view: show width and length
                x1, y1 = pos.x, pos.y
                x2, y2 = pos.x + length, pos.y
                entities.append({
                    "type": "LINE",
                    "start": (x1, y1),
                    "end": (x2, y2),
                })
            elif view == "top":
                # Top view: show width and length
                x1, z1 = pos.x, pos.z
                x2, z2 = pos.x + length, pos.z
                entities.append({
                    "type": "LINE",
                    "start": (x1, z1),
                    "end": (x2, z2),
                })
            elif view == "side":
                # Side view: show height and length
                y1, z1 = pos.y, pos.z
                y2, z2 = pos.y + length, pos.z
                entities.append({
                    "type": "LINE",
                    "start": (y1, z1),
                    "end": (y2, z2),
                })
        
        elif comp_type in ["rib", "former"]:
            # Planar component: project as outline
            width = dims.get("width", 1.0)
            height = dims.get("height", 1.0)
            
            if view == "front":
                # Front view: show as rectangle
                x1, y1 = pos.x - width/2, pos.y - height/2
                x2, y2 = pos.x + width/2, pos.y + height/2
                entities.append({
                    "type": "RECTANGLE",
                    "min": (x1, y1),
                    "max": (x2, y2),
                })
            # Similar for other views...
        
        return entities

