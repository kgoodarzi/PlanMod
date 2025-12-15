"""
Region segmentation for PlanMod.

Uses VLM to segment drawings into distinct regions (views, details, etc.).
"""

import io
import logging
from typing import Optional

import numpy as np
from PIL import Image

from backend.vlm_client.base import VLMClient, Region

logger = logging.getLogger(__name__)


class RegionSegmenter:
    """
    Segments drawings into distinct regions using VLM.
    
    Identifies:
    - Orthographic views (top, side, front)
    - Detail views
    - Section views
    - Title blocks
    - Parts lists
    - Individual component drawings
    """
    
    # Expected region types for model aircraft plans
    EXPECTED_REGION_TYPES = [
        "top_view",
        "side_view",
        "front_view",
        "section_view",
        "detail_view",
        "title_block",
        "parts_list",
        "component",
        "fuselage",
        "wing",
        "tail",
        "notes",
    ]
    
    def __init__(self, vlm_client: VLMClient):
        """
        Initialize region segmenter.
        
        Args:
            vlm_client: VLM client for image analysis
        """
        self.vlm_client = vlm_client
    
    async def segment(
        self,
        image: np.ndarray,
        expected_types: Optional[list[str]] = None,
    ) -> list[Region]:
        """
        Segment image into regions.
        
        Args:
            image: Input image as numpy array
            expected_types: Optional list of expected region types
            
        Returns:
            List of detected regions
        """
        logger.info("Segmenting image into regions")
        
        # Convert to bytes for VLM
        image_bytes = self._image_to_bytes(image)
        
        # Get VLM segmentation
        response = await self.vlm_client.segment_regions(
            image_bytes,
            expected_types or self.EXPECTED_REGION_TYPES,
        )
        
        if not response.success:
            logger.warning(f"VLM segmentation failed: {response.error}")
            # Fall back to simple grid-based segmentation
            return self._fallback_segmentation(image)
        
        regions = response.regions
        
        # Post-process regions
        regions = self._merge_overlapping_regions(regions)
        regions = self._filter_small_regions(regions, min_area=0.01)
        
        logger.info(f"Segmented into {len(regions)} regions")
        
        return regions
    
    def _image_to_bytes(self, image: np.ndarray) -> bytes:
        """Convert numpy image to PNG bytes."""
        pil_image = Image.fromarray(image)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    
    def _fallback_segmentation(self, image: np.ndarray) -> list[Region]:
        """
        Simple fallback segmentation when VLM fails.
        
        Divides image into quadrants and treats each as a potential region.
        """
        logger.info("Using fallback grid-based segmentation")
        
        regions = [
            Region(
                x=0.0,
                y=0.0,
                width=1.0,
                height=1.0,
                label="Full Drawing",
                confidence=0.5,
                description="Full drawing area (VLM segmentation unavailable)",
                attributes={"type": "unknown"},
            )
        ]
        
        return regions
    
    def _merge_overlapping_regions(
        self,
        regions: list[Region],
        overlap_threshold: float = 0.5,
    ) -> list[Region]:
        """
        Merge regions that overlap significantly.
        
        Args:
            regions: List of regions
            overlap_threshold: Minimum overlap ratio to merge
            
        Returns:
            Merged region list
        """
        if len(regions) <= 1:
            return regions
        
        merged = []
        used = set()
        
        for i, region1 in enumerate(regions):
            if i in used:
                continue
            
            # Find overlapping regions
            to_merge = [region1]
            
            for j, region2 in enumerate(regions[i + 1:], i + 1):
                if j in used:
                    continue
                
                overlap = self._calculate_overlap(region1, region2)
                
                if overlap > overlap_threshold:
                    to_merge.append(region2)
                    used.add(j)
            
            # Merge if multiple regions
            if len(to_merge) > 1:
                merged_region = self._merge_region_group(to_merge)
                merged.append(merged_region)
            else:
                merged.append(region1)
            
            used.add(i)
        
        return merged
    
    def _calculate_overlap(self, r1: Region, r2: Region) -> float:
        """Calculate overlap ratio between two regions."""
        # Calculate intersection
        x1 = max(r1.x, r2.x)
        y1 = max(r1.y, r2.y)
        x2 = min(r1.x + r1.width, r2.x + r2.width)
        y2 = min(r1.y + r1.height, r2.y + r2.height)
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection_area = (x2 - x1) * (y2 - y1)
        
        # Calculate union
        area1 = r1.width * r1.height
        area2 = r2.width * r2.height
        union_area = area1 + area2 - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
    def _merge_region_group(self, regions: list[Region]) -> Region:
        """Merge a group of overlapping regions."""
        # Calculate bounding box
        x = min(r.x for r in regions)
        y = min(r.y for r in regions)
        x2 = max(r.x + r.width for r in regions)
        y2 = max(r.y + r.height for r in regions)
        
        # Use highest confidence region's label
        best_region = max(regions, key=lambda r: r.confidence)
        
        return Region(
            x=x,
            y=y,
            width=x2 - x,
            height=y2 - y,
            label=best_region.label,
            confidence=best_region.confidence,
            description=f"Merged from {len(regions)} regions",
            attributes=best_region.attributes,
        )
    
    def _filter_small_regions(
        self,
        regions: list[Region],
        min_area: float = 0.01,
    ) -> list[Region]:
        """
        Filter out very small regions.
        
        Args:
            regions: List of regions
            min_area: Minimum area as fraction of image (0.01 = 1%)
            
        Returns:
            Filtered region list
        """
        return [
            r for r in regions
            if r.width * r.height >= min_area
        ]
    
    async def refine_region(
        self,
        image: np.ndarray,
        region: Region,
    ) -> Region:
        """
        Refine a single region's classification.
        
        Args:
            image: Full image
            region: Region to refine
            
        Returns:
            Refined region
        """
        # Crop region from image
        h, w = image.shape[:2]
        x1 = int(region.x * w)
        y1 = int(region.y * h)
        x2 = int((region.x + region.width) * w)
        y2 = int((region.y + region.height) * h)
        
        crop = image[y1:y2, x1:x2]
        
        if crop.size == 0:
            return region
        
        # Get more detailed analysis of the cropped region
        crop_bytes = self._image_to_bytes(crop)
        
        response = await self.vlm_client.describe_drawing(crop_bytes)
        
        if response.success and response.structured_data:
            data = response.structured_data
            
            # Update region with refined information
            region.description = data.get("description", region.description)
            region.attributes["refined"] = True
            region.attributes["subject"] = data.get("subject", "")
            region.attributes["views"] = data.get("views_identified", [])
        
        return region


