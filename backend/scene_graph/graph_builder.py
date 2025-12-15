"""
Scene graph construction and relationship building.
"""

import logging
from typing import Optional

from backend.shared.models import SceneGraph, Relationship, ComponentType

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds and enriches scene graphs.
    
    Creates relationships between:
    - Views and components
    - Components and annotations
    - Components and geometry entities
    """
    
    def build_relationships(self, scene_graph: SceneGraph) -> SceneGraph:
        """
        Build relationships between scene graph elements.
        
        Args:
            scene_graph: Scene graph to process
            
        Returns:
            Scene graph with relationships added
        """
        logger.info("Building scene graph relationships")
        
        # Build view-component relationships
        for view in scene_graph.views:
            for comp_id in view.component_ids:
                rel = Relationship(
                    relationship_type="contains",
                    source_id=view.id,
                    target_id=comp_id,
                )
                scene_graph.relationships.append(rel)
        
        # Build component-component relationships (adjacency)
        for i, comp1 in enumerate(scene_graph.components):
            for comp2 in scene_graph.components[i + 1:]:
                if comp1.view_id == comp2.view_id:
                    # Check if bounds are adjacent
                    if self._are_adjacent(comp1.bounds, comp2.bounds):
                        rel = Relationship(
                            relationship_type="adjacent_to",
                            source_id=comp1.id,
                            target_id=comp2.id,
                        )
                        scene_graph.relationships.append(rel)
        
        # Build component-annotation relationships
        for annotation in scene_graph.annotations:
            nearest_comp = self._find_nearest_component(
                annotation.bounds.center,
                scene_graph.components,
            )
            if nearest_comp:
                annotation.associated_component_id = nearest_comp.id
                rel = Relationship(
                    relationship_type="labels",
                    source_id=annotation.id,
                    target_id=nearest_comp.id,
                )
                scene_graph.relationships.append(rel)
        
        logger.info(f"Built {len(scene_graph.relationships)} relationships")
        
        return scene_graph
    
    def assign_dxf_mapping(self, scene_graph: SceneGraph) -> SceneGraph:
        """
        Assign DXF layer names and block names to elements.
        
        Args:
            scene_graph: Scene graph to process
            
        Returns:
            Scene graph with DXF mappings
        """
        logger.info("Assigning DXF mappings")
        
        # Assign view layers
        for view in scene_graph.views:
            view_type = view.view_type.value.upper()
            # Unique layer per view instance
            layer_name = f"VIEW_{view_type}_{view.id[:8]}"
            
            # Store in entity references
            for entity in scene_graph.entities:
                if entity.view_id == view.id:
                    entity.layer = f"VIEW_{view_type}"
        
        # Assign component layers and blocks
        component_counters: dict[str, int] = {}
        
        for component in scene_graph.components:
            comp_type = component.component_type.value.upper()
            
            # Increment counter for this type
            if comp_type not in component_counters:
                component_counters[comp_type] = 0
            component_counters[comp_type] += 1
            
            # Generate layer name
            component.dxf_layer = f"COMP_{comp_type}"
            
            # Generate block name
            component.dxf_block_name = f"{comp_type}_{component_counters[comp_type]:03d}"
            
            if component.name:
                # Use provided name if available
                safe_name = component.name.upper().replace(" ", "_")[:20]
                component.dxf_block_name = safe_name
        
        return scene_graph
    
    def _are_adjacent(self, bounds1, bounds2, threshold: float = 50) -> bool:
        """Check if two bounding boxes are adjacent."""
        # Check horizontal adjacency
        h_gap = max(0, max(bounds1.x, bounds2.x) - min(bounds1.x2, bounds2.x2))
        
        # Check vertical adjacency  
        v_gap = max(0, max(bounds1.y, bounds2.y) - min(bounds1.y2, bounds2.y2))
        
        return h_gap < threshold or v_gap < threshold
    
    def _find_nearest_component(
        self,
        point: tuple,
        components: list,
        max_distance: float = 100,
    ) -> Optional[any]:
        """Find nearest component to a point."""
        nearest = None
        min_dist = float('inf')
        
        for comp in components:
            center = comp.bounds.center
            dist = ((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2) ** 0.5
            
            if dist < min_dist and dist < max_distance:
                min_dist = dist
                nearest = comp
        
        return nearest


