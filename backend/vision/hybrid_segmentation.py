"""
Hybrid Segmentation Pipeline

Uses Classical CV for precise boundaries + VLM for semantic classification.

Strategy:
1. CV detects regions/contours (PRECISE boundaries)
2. VLM classifies what each region IS (SEMANTIC meaning)
3. Combine for accurate, labeled segmentation
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DetectedRegion:
    """A region detected by CV with semantic label from VLM."""
    region_id: int
    contour: np.ndarray
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    area: float
    centroid: Tuple[int, int]
    aspect_ratio: float
    solidity: float  # Filled area / convex hull area
    
    # Classification (from pattern matching or VLM)
    category: str = "unknown"
    confidence: float = 0.0
    label: str = ""
    
    # Visual properties
    fill_color: Tuple[int, int, int] = (128, 128, 128)
    is_filled: bool = False  # Shape vs line


class HybridSegmenter:
    """
    Combines CV contour detection with pattern-based classification.
    
    For model aircraft plans:
    - Rectangles with specific aspect ratios → planform regions
    - Airfoil shapes with holes → ribs
    - Long thin rectangles → spars
    - Closed irregular shapes → formers
    """
    
    # Pattern definitions for model aircraft components
    PATTERNS = {
        "planform_region": {
            "description": "Wing/elevator plan view region",
            "aspect_ratio_range": (1.5, 8.0),  # Long rectangles
            "min_area_pct": 5.0,  # At least 5% of image
            "solidity_range": (0.85, 1.0),  # Nearly rectangular
            "color_bgr": (0, 255, 0),  # Green
        },
        "rib_template": {
            "description": "Airfoil cross-section shape",
            "aspect_ratio_range": (2.0, 6.0),
            "min_area_pct": 0.3,
            "max_area_pct": 3.0,
            "solidity_range": (0.5, 0.85),  # Has holes
            "color_bgr": (0, 0, 255),  # Red
        },
        "spar": {
            "description": "Long structural member",
            "aspect_ratio_range": (8.0, 100.0),  # Very elongated
            "min_area_pct": 0.1,
            "solidity_range": (0.9, 1.0),  # Solid rectangle
            "color_bgr": (255, 0, 0),  # Blue
        },
        "strengthening": {
            "description": "Oval/elliptical lightening hole structure",
            "aspect_ratio_range": (1.2, 3.0),
            "min_area_pct": 0.2,
            "max_area_pct": 2.0,
            "solidity_range": (0.4, 0.7),  # Has large holes
            "color_bgr": (255, 255, 0),  # Cyan
        },
        "former": {
            "description": "Fuselage cross-section bulkhead",
            "aspect_ratio_range": (0.3, 2.0),  # Roughly square-ish
            "min_area_pct": 0.2,
            "max_area_pct": 3.0,
            "solidity_range": (0.6, 0.95),
            "color_bgr": (0, 0, 255),  # Red
        },
        "misc": {
            "description": "Other components",
            "color_bgr": (128, 128, 128),  # Gray
        },
    }
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.regions: List[DetectedRegion] = []
    
    def detect_regions(self, image: np.ndarray) -> List[DetectedRegion]:
        """
        Detect all closed regions in the image using CV.
        
        Returns list of DetectedRegion with geometric properties.
        """
        self.regions = []
        h, w = image.shape[:2]
        total_area = h * w
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Multiple detection strategies
        all_contours = []
        
        # Strategy 1: Binary threshold
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        contours1, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        all_contours.extend(contours1)
        
        # Strategy 2: Adaptive threshold (catches more detail)
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY_INV, 11, 2)
        contours2, _ = cv2.findContours(adaptive, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        all_contours.extend(contours2)
        
        # Strategy 3: Edge detection
        edges = cv2.Canny(gray, 50, 150)
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours3, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        all_contours.extend(contours3)
        
        # Deduplicate and filter contours
        seen_centroids = set()
        region_id = 0
        
        for contour in all_contours:
            area = cv2.contourArea(contour)
            
            # Skip tiny contours
            if area < total_area * 0.0005:  # < 0.05% of image
                continue
            
            # Compute properties
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
                
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Deduplicate by centroid (within 20 pixels)
            centroid_key = (cx // 20, cy // 20)
            if centroid_key in seen_centroids:
                continue
            seen_centroids.add(centroid_key)
            
            # Bounding box
            x, y, bw, bh = cv2.boundingRect(contour)
            
            # Aspect ratio
            aspect_ratio = max(bw, bh) / max(min(bw, bh), 1)
            
            # Solidity
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            
            region = DetectedRegion(
                region_id=region_id,
                contour=contour,
                bbox=(x, y, bw, bh),
                area=area,
                centroid=(cx, cy),
                aspect_ratio=aspect_ratio,
                solidity=solidity,
            )
            
            self.regions.append(region)
            region_id += 1
        
        if self.debug:
            print(f"Detected {len(self.regions)} regions")
        
        return self.regions
    
    def classify_by_geometry(self, image: np.ndarray) -> List[DetectedRegion]:
        """
        Classify detected regions based on geometric patterns.
        
        This is fast pattern matching - no VLM needed.
        """
        if not self.regions:
            self.detect_regions(image)
        
        h, w = image.shape[:2]
        total_area = h * w
        
        for region in self.regions:
            area_pct = (region.area / total_area) * 100
            
            best_match = "misc"
            best_confidence = 0.0
            
            for pattern_name, pattern in self.PATTERNS.items():
                if pattern_name == "misc":
                    continue
                
                confidence = 0.0
                checks = 0
                
                # Check aspect ratio
                if "aspect_ratio_range" in pattern:
                    min_ar, max_ar = pattern["aspect_ratio_range"]
                    if min_ar <= region.aspect_ratio <= max_ar:
                        confidence += 0.3
                    checks += 1
                
                # Check area
                if "min_area_pct" in pattern:
                    if area_pct >= pattern["min_area_pct"]:
                        confidence += 0.2
                    checks += 1
                
                if "max_area_pct" in pattern:
                    if area_pct <= pattern["max_area_pct"]:
                        confidence += 0.2
                    checks += 1
                
                # Check solidity
                if "solidity_range" in pattern:
                    min_sol, max_sol = pattern["solidity_range"]
                    if min_sol <= region.solidity <= max_sol:
                        confidence += 0.3
                    checks += 1
                
                # Normalize
                if checks > 0:
                    confidence = confidence / (checks * 0.25)  # Max possible per check
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = pattern_name
            
            region.category = best_match
            region.confidence = best_confidence
            region.fill_color = self.PATTERNS.get(best_match, {}).get("color_bgr", (128, 128, 128))
        
        return self.regions
    
    def detect_lines(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect lines (spars, rib positions) using Hough transform.
        
        Returns list of line segments.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                                 minLineLength=50, maxLineGap=10)
        
        detected_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                angle = np.arctan2(y2-y1, x2-x1) * 180 / np.pi
                
                # Classify by angle
                if abs(angle) < 10 or abs(angle) > 170:
                    line_type = "horizontal"  # spar
                elif 80 < abs(angle) < 100:
                    line_type = "vertical"  # rib position
                else:
                    line_type = "diagonal"
                
                detected_lines.append({
                    "start": (x1, y1),
                    "end": (x2, y2),
                    "length": length,
                    "angle": angle,
                    "type": line_type,
                })
        
        return detected_lines
    
    def render_segmentation(self, image: np.ndarray, 
                            fill_alpha: float = 0.4) -> np.ndarray:
        """
        Render detected regions with colored fills (like reference image).
        """
        result = image.copy()
        overlay = image.copy()
        
        # Sort by area (largest first so smaller overlay on top)
        sorted_regions = sorted(self.regions, key=lambda r: r.area, reverse=True)
        
        for region in sorted_regions:
            color = region.fill_color
            
            # Fill the contour
            cv2.drawContours(overlay, [region.contour], -1, color, -1)
            
            # Draw outline
            cv2.drawContours(result, [region.contour], -1, color, 2)
            
            # Add label
            cx, cy = region.centroid
            label = f"{region.category}"
            cv2.putText(result, label, (cx - 30, cy), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        
        # Blend
        result = cv2.addWeighted(overlay, fill_alpha, result, 1 - fill_alpha, 0)
        
        return result
    
    def create_reference_style(self, image: np.ndarray,
                                category_colors: Dict[str, Tuple[int, int, int]] = None
                                ) -> np.ndarray:
        """
        Create reference-style visualization with filled regions.
        
        This mimics the user's training reference images.
        """
        if category_colors is None:
            category_colors = {
                "planform_region": (0, 255, 0),    # Green
                "rib_template": (0, 0, 255),       # Red (BGR)
                "spar": (255, 0, 0),               # Blue
                "strengthening": (255, 255, 0),   # Cyan
                "former": (0, 0, 255),            # Red
                "misc": (128, 128, 128),          # Gray
            }
        
        # Start with white background
        result = np.ones_like(image) * 255
        
        # Draw original lines/edges in light gray
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Find edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Draw edges on result
        result[edges > 0] = [200, 200, 200]
        
        # Fill regions by category
        for region in sorted(self.regions, key=lambda r: r.area, reverse=True):
            color = category_colors.get(region.category, (128, 128, 128))
            cv2.drawContours(result, [region.contour], -1, color, -1)
        
        return result


def demo_hybrid_segmentation(image_path: str, output_path: str):
    """
    Demonstrate hybrid segmentation on a plan image.
    """
    print(f"Loading: {image_path}")
    image = cv2.imread(image_path)
    if image is None:
        print("Failed to load image")
        return
    
    segmenter = HybridSegmenter(debug=True)
    
    # Detect and classify regions
    print("Detecting regions...")
    segmenter.detect_regions(image)
    
    print("Classifying by geometry...")
    segmenter.classify_by_geometry(image)
    
    # Print results
    by_category = {}
    for region in segmenter.regions:
        cat = region.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(region)
    
    print("\nClassification Results:")
    for cat, regions in sorted(by_category.items()):
        print(f"  {cat}: {len(regions)} regions")
    
    # Render
    print("\nRendering segmentation...")
    result = segmenter.render_segmentation(image)
    
    cv2.imwrite(output_path, result)
    print(f"Saved: {output_path}")
    
    return segmenter


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = "output/pdf_page2_raster.png"
    
    output_path = "output/cv_segmentation.png"
    demo_hybrid_segmentation(input_path, output_path)


