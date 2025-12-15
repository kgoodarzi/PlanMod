"""
VLM-Guided Computer Vision Pipeline

Uses VLM for high-level pattern recognition (WHAT and WHERE approximately),
then CV for precise boundary detection (EXACT pixels).

This combines the best of both:
- VLM: Semantic understanding, label reading, pattern recognition
- CV: Pixel-perfect contours, flood fill, exact measurements
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class VLMGuidance:
    """Guidance from VLM about what to look for."""
    category: str
    approximate_location: str  # "top-left", "center", "right-column", etc.
    description: str
    expected_shape: str  # "rectangle", "airfoil", "line", etc.
    labels_to_find: List[str]  # ["R1", "R2", "WT", etc.]


class VLMGuidedCV:
    """
    Two-stage pipeline:
    1. VLM provides high-level guidance (regions, labels, patterns)
    2. CV finds exact boundaries using that guidance
    """
    
    # Grid for approximate locations (9 zones)
    LOCATION_GRID = {
        "top-left": (0, 0, 0.33, 0.33),
        "top-center": (0.33, 0, 0.67, 0.33),
        "top-right": (0.67, 0, 1.0, 0.33),
        "middle-left": (0, 0.33, 0.33, 0.67),
        "center": (0.33, 0.33, 0.67, 0.67),
        "middle-right": (0.67, 0.33, 1.0, 0.67),
        "bottom-left": (0, 0.67, 0.33, 1.0),
        "bottom-center": (0.33, 0.67, 0.67, 1.0),
        "bottom-right": (0.67, 0.67, 1.0, 1.0),
        # Extended locations
        "left-column": (0, 0, 0.4, 1.0),
        "right-column": (0.6, 0, 1.0, 1.0),
        "top-half": (0, 0, 1.0, 0.5),
        "bottom-half": (0, 0.5, 1.0, 1.0),
    }
    
    # Color mapping
    CATEGORY_COLORS_BGR = {
        "wing_planform": (0, 255, 0),      # Green
        "elevator_planform": (0, 255, 0),  # Green
        "rib": (0, 0, 255),                # Red
        "spar": (255, 0, 0),               # Blue
        "strengthening": (255, 255, 0),    # Cyan
        "tail": (255, 0, 255),             # Magenta
        "former": (0, 0, 255),             # Red
        "fuselage_side": (255, 0, 0),      # Blue
        "landing_gear": (200, 180, 255),   # Pink
        "motor": (0, 165, 255),            # Orange
        "misc": (128, 128, 128),           # Gray
    }
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        self.guidance: List[VLMGuidance] = []
        self.detected_regions: List[Dict] = []
    
    def set_guidance_from_vlm_response(self, vlm_components: List[Dict]):
        """
        Convert VLM component list to guidance for CV.
        """
        self.guidance = []
        
        for comp in vlm_components:
            # Extract approximate location from bbox
            x_pct = comp.get("x_pct", 50)
            y_pct = comp.get("y_pct", 50)
            
            # Map to grid location
            location = self._pct_to_location(x_pct, y_pct)
            
            guidance = VLMGuidance(
                category=comp.get("category", "misc"),
                approximate_location=location,
                description=comp.get("description", ""),
                expected_shape=comp.get("geometry_type", "shape"),
                labels_to_find=[comp.get("id", "")],
            )
            self.guidance.append(guidance)
        
        if self.debug:
            print(f"Set {len(self.guidance)} guidance hints from VLM")
    
    def _pct_to_location(self, x_pct: float, y_pct: float) -> str:
        """Map percentage coordinates to grid location."""
        x_pct = x_pct / 100.0
        y_pct = y_pct / 100.0
        
        if x_pct < 0.33:
            col = "left"
        elif x_pct < 0.67:
            col = "center"
        else:
            col = "right"
        
        if y_pct < 0.33:
            row = "top"
        elif y_pct < 0.67:
            row = "middle"
        else:
            row = "bottom"
        
        return f"{row}-{col}"
    
    def find_closed_shapes_in_region(self, image: np.ndarray,
                                      location: str,
                                      min_area_pct: float = 0.1) -> List[np.ndarray]:
        """
        Find closed contours in a specific region of the image.
        """
        h, w = image.shape[:2]
        
        # Get region bounds
        if location in self.LOCATION_GRID:
            x1_pct, y1_pct, x2_pct, y2_pct = self.LOCATION_GRID[location]
        else:
            x1_pct, y1_pct, x2_pct, y2_pct = 0, 0, 1, 1
        
        x1 = int(x1_pct * w)
        y1 = int(y1_pct * h)
        x2 = int(x2_pct * w)
        y2 = int(y2_pct * h)
        
        # Extract region
        region = image[y1:y2, x1:x2]
        
        if len(region.shape) == 3:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        else:
            gray = region.copy()
        
        # Find contours
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter by area and offset coordinates back to full image
        min_area = (h * w) * (min_area_pct / 100.0)
        result = []
        
        for contour in contours:
            if cv2.contourArea(contour) >= min_area:
                # Offset contour to full image coordinates
                contour = contour + np.array([x1, y1])
                result.append(contour)
        
        return result
    
    def find_text_labels(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Find text labels in the image using morphological operations.
        
        Returns approximate bounding boxes of text regions.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Threshold
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Use morphology to find text regions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter: text regions are typically small and wide
            aspect = w / max(h, 1)
            area = w * h
            
            if 50 < area < 10000 and 0.5 < aspect < 10:
                text_regions.append({
                    "bbox": (x, y, w, h),
                    "center": (x + w//2, y + h//2),
                })
        
        return text_regions
    
    def flood_fill_from_seed(self, image: np.ndarray, 
                             seed_point: Tuple[int, int],
                             tolerance: int = 20) -> np.ndarray:
        """
        Flood fill from a seed point to get exact region mask.
        
        This is how to get pixel-perfect boundaries!
        """
        h, w = image.shape[:2]
        
        # Create mask (must be 2 pixels larger than image)
        mask = np.zeros((h + 2, w + 2), np.uint8)
        
        # Convert to BGR if needed
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        
        # Flood fill
        flood_image = image.copy()
        cv2.floodFill(flood_image, mask, seed_point, (255, 0, 255),
                      loDiff=(tolerance,) * 3, upDiff=(tolerance,) * 3)
        
        # Extract filled region
        filled_mask = mask[1:-1, 1:-1]
        
        return filled_mask
    
    def segment_with_guidance(self, image: np.ndarray) -> np.ndarray:
        """
        Use VLM guidance to segment image with CV precision.
        """
        h, w = image.shape[:2]
        
        # Result image
        result = image.copy()
        overlay = np.zeros_like(image)
        
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Process each guidance hint
        for guide in self.guidance:
            color = self.CATEGORY_COLORS_BGR.get(guide.category, (128, 128, 128))
            
            if guide.expected_shape == "shape":
                # Find closed shapes in the approximate region
                contours = self.find_closed_shapes_in_region(
                    image, guide.approximate_location, min_area_pct=0.1
                )
                
                for contour in contours:
                    cv2.drawContours(overlay, [contour], -1, color, -1)
            
            elif guide.expected_shape == "line":
                # Find lines in the region
                region_bounds = self.LOCATION_GRID.get(guide.approximate_location, (0, 0, 1, 1))
                x1, y1, x2, y2 = [int(v * (w if i % 2 == 0 else h)) 
                                  for i, v in enumerate(region_bounds)]
                
                region = gray[y1:y2, x1:x2]
                edges = cv2.Canny(region, 50, 150)
                lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=30, maxLineGap=5)
                
                if lines is not None:
                    for line in lines:
                        lx1, ly1, lx2, ly2 = line[0]
                        cv2.line(overlay, (x1 + lx1, y1 + ly1), (x1 + lx2, y1 + ly2), color, 3)
        
        # Blend overlay with original
        alpha = 0.4
        result = cv2.addWeighted(overlay, alpha, result, 1.0, 0)
        
        return result
    
    def segment_by_flood_fill(self, image: np.ndarray,
                               seed_categories: Dict[str, List[Tuple[int, int]]]) -> np.ndarray:
        """
        Segment using flood fill from seed points.
        
        seed_categories: {"rib": [(x1,y1), (x2,y2)], "spar": [(x3,y3)], ...}
        
        This is the most accurate method when you have seed points!
        """
        result = image.copy()
        
        for category, seeds in seed_categories.items():
            color = self.CATEGORY_COLORS_BGR.get(category, (128, 128, 128))
            
            for seed in seeds:
                mask = self.flood_fill_from_seed(image, seed)
                
                # Apply color to mask
                result[mask > 0] = color
        
        return result


def get_vlm_pattern_recognition_prompt() -> str:
    """
    VLM prompt designed for pattern recognition (approximate locations).
    
    Instead of asking for exact coordinates, we ask for:
    - Which grid zone contains each component
    - What pattern/shape to look for
    - What labels to search for nearby
    """
    return """Analyze this model aircraft plan drawing as a PATTERN RECOGNITION task.

For each component you identify, tell me:
1. GRID ZONE: Which area of the image (use 3x3 grid: top-left, top-center, top-right, middle-left, center, middle-right, bottom-left, bottom-center, bottom-right)
2. SHAPE PATTERN: What shape to look for (rectangle, airfoil, oval, line, etc.)
3. LABELS NEARBY: Any text labels near this component (R1, WT, F1, etc.)
4. CATEGORY: What type of component (rib, spar, former, planform, etc.)

Example output format:
[
  {"grid_zone": "top-left", "pattern": "tall_rectangle", "labels": ["R1", "R2"], "category": "rib"},
  {"grid_zone": "center", "pattern": "long_horizontal_line", "labels": ["1/8x3/16 bass"], "category": "spar"},
  {"grid_zone": "middle-left", "pattern": "large_rectangle", "labels": ["Left wing"], "category": "wing_planform"}
]

Focus on APPROXIMATE locations - CV will find exact boundaries.
What patterns and labels do you see in each zone?"""


# Example usage demonstrating the hybrid approach
def demo_vlm_guided_cv(image_path: str):
    """
    Demonstrate the VLM-guided CV approach.
    """
    print("=" * 60)
    print("VLM-Guided Computer Vision Pipeline")
    print("=" * 60)
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load: {image_path}")
        return
    
    h, w = image.shape[:2]
    print(f"Image: {w}x{h}")
    
    # Example: Manual guidance (in real use, this comes from VLM)
    example_guidance = [
        {"category": "wing_planform", "x_pct": 20, "y_pct": 50, "geometry_type": "shape"},
        {"category": "wing_planform", "x_pct": 55, "y_pct": 50, "geometry_type": "shape"},
        {"category": "rib", "x_pct": 30, "y_pct": 5, "geometry_type": "shape"},
        {"category": "spar", "x_pct": 10, "y_pct": 50, "geometry_type": "line"},
    ]
    
    pipeline = VLMGuidedCV(debug=True)
    pipeline.set_guidance_from_vlm_response(example_guidance)
    
    # Segment
    result = pipeline.segment_with_guidance(image)
    
    output_path = "output/vlm_guided_cv_result.png"
    cv2.imwrite(output_path, result)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    demo_vlm_guided_cv("output/pdf_page2_raster.png")


