"""
Classical Computer Vision detector for PlanMod.

Uses OpenCV for line, edge, and shape detection.
"""

import logging
from typing import Any, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CVDetector:
    """
    Classical CV-based detector for drawing analysis.
    
    Detects:
    - Lines (using Hough transform)
    - Edges (using Canny)
    - Contours
    - Circles and arcs
    """
    
    def __init__(
        self,
        canny_low: int = 50,
        canny_high: int = 150,
        hough_threshold: int = 80,
        min_line_length: int = 30,
        max_line_gap: int = 10,
    ):
        """
        Initialize CV detector.
        
        Args:
            canny_low: Canny edge detection low threshold
            canny_high: Canny edge detection high threshold
            hough_threshold: Hough line detection threshold
            min_line_length: Minimum line length for detection
            max_line_gap: Maximum gap between line segments
        """
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
    
    def detect(self, image: np.ndarray) -> dict[str, Any]:
        """
        Run full detection pipeline on image.
        
        Args:
            image: Input image (RGB or grayscale)
            
        Returns:
            Dictionary with detection results
        """
        logger.info(f"Running CV detection on image {image.shape}")
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Detect edges
        edges = self.detect_edges(gray)
        
        # Detect lines
        lines = self.detect_lines(edges)
        
        # Detect contours
        contours = self.detect_contours(edges)
        
        # Detect circles
        circles = self.detect_circles(gray)
        
        # Find intersections
        intersections = self.find_intersections(lines)
        
        logger.info(
            f"CV detection complete: {len(lines)} lines, "
            f"{len(contours)} contours, {len(circles)} circles"
        )
        
        return {
            "edges": edges,
            "lines": lines,
            "contours": contours,
            "circles": circles,
            "intersections": intersections,
        }
    
    def detect_edges(self, gray: np.ndarray) -> np.ndarray:
        """
        Detect edges using Canny edge detection.
        
        Args:
            gray: Grayscale image
            
        Returns:
            Edge image
        """
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply Canny edge detection
        edges = cv2.Canny(blurred, self.canny_low, self.canny_high)
        
        return edges
    
    def detect_lines(
        self,
        edges: np.ndarray,
        probabilistic: bool = True,
    ) -> list[dict]:
        """
        Detect lines using Hough transform.
        
        Args:
            edges: Edge image from Canny
            probabilistic: Use probabilistic Hough (default) or standard
            
        Returns:
            List of line dictionaries with start/end points
        """
        lines = []
        
        if probabilistic:
            # Probabilistic Hough Transform
            detected = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=self.hough_threshold,
                minLineLength=self.min_line_length,
                maxLineGap=self.max_line_gap,
            )
            
            if detected is not None:
                for line in detected:
                    x1, y1, x2, y2 = line[0]
                    lines.append({
                        "start": (int(x1), int(y1)),
                        "end": (int(x2), int(y2)),
                        "length": np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2),
                        "angle": np.degrees(np.arctan2(y2 - y1, x2 - x1)),
                    })
        else:
            # Standard Hough Transform
            detected = cv2.HoughLines(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=self.hough_threshold,
            )
            
            if detected is not None:
                for line in detected:
                    rho, theta = line[0]
                    a = np.cos(theta)
                    b = np.sin(theta)
                    x0 = a * rho
                    y0 = b * rho
                    
                    # Extend line across image
                    x1 = int(x0 + 1000 * (-b))
                    y1 = int(y0 + 1000 * (a))
                    x2 = int(x0 - 1000 * (-b))
                    y2 = int(y0 - 1000 * (a))
                    
                    lines.append({
                        "start": (x1, y1),
                        "end": (x2, y2),
                        "rho": float(rho),
                        "theta": float(theta),
                        "angle": np.degrees(theta),
                    })
        
        return lines
    
    def detect_contours(
        self,
        edges: np.ndarray,
        min_area: int = 100,
    ) -> list[dict]:
        """
        Detect contours in edge image.
        
        Args:
            edges: Edge image
            min_area: Minimum contour area to keep
            
        Returns:
            List of contour dictionaries
        """
        # Find contours
        contours, hierarchy = cv2.findContours(
            edges,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        
        result = []
        
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            if area < min_area:
                continue
            
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Get perimeter
            perimeter = cv2.arcLength(contour, closed=True)
            
            # Approximate polygon
            epsilon = 0.02 * perimeter
            approx = cv2.approxPolyDP(contour, epsilon, closed=True)
            
            # Determine shape
            num_vertices = len(approx)
            shape = self._classify_shape(num_vertices, area, w, h)
            
            result.append({
                "id": i,
                "area": float(area),
                "perimeter": float(perimeter),
                "bounds": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                "vertices": num_vertices,
                "shape": shape,
                "points": contour.tolist(),
                "hierarchy": hierarchy[0][i].tolist() if hierarchy is not None else None,
            })
        
        return result
    
    def detect_circles(
        self,
        gray: np.ndarray,
        min_radius: int = 10,
        max_radius: int = 100,
    ) -> list[dict]:
        """
        Detect circles using Hough Circle Transform.
        
        Args:
            gray: Grayscale image
            min_radius: Minimum circle radius
            max_radius: Maximum circle radius
            
        Returns:
            List of circle dictionaries
        """
        # Apply blur
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        
        # Detect circles
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=30,
            param1=50,
            param2=30,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        
        result = []
        
        if circles is not None:
            circles = np.uint16(np.around(circles))
            
            for circle in circles[0]:
                result.append({
                    "center": (int(circle[0]), int(circle[1])),
                    "radius": int(circle[2]),
                })
        
        return result
    
    def find_intersections(
        self,
        lines: list[dict],
        tolerance: int = 5,
    ) -> list[dict]:
        """
        Find intersections between detected lines.
        
        Args:
            lines: List of line dictionaries
            tolerance: Tolerance for considering lines as intersecting
            
        Returns:
            List of intersection points
        """
        intersections = []
        
        for i, line1 in enumerate(lines):
            for j, line2 in enumerate(lines[i + 1:], i + 1):
                point = self._line_intersection(
                    line1["start"], line1["end"],
                    line2["start"], line2["end"],
                )
                
                if point is not None:
                    intersections.append({
                        "point": point,
                        "line_ids": (i, j),
                    })
        
        return intersections
    
    def _classify_shape(
        self,
        num_vertices: int,
        area: float,
        width: int,
        height: int,
    ) -> str:
        """Classify shape based on properties."""
        aspect_ratio = width / height if height > 0 else 1
        
        if num_vertices == 3:
            return "triangle"
        elif num_vertices == 4:
            if 0.95 <= aspect_ratio <= 1.05:
                return "square"
            return "rectangle"
        elif num_vertices == 5:
            return "pentagon"
        elif num_vertices == 6:
            return "hexagon"
        elif num_vertices > 6:
            # Check if it's approximately circular
            circularity = 4 * np.pi * area / ((2 * np.pi * max(width, height) / 2) ** 2)
            if circularity > 0.7:
                return "circle"
            return "polygon"
        
        return "unknown"
    
    def _line_intersection(
        self,
        p1: tuple,
        p2: tuple,
        p3: tuple,
        p4: tuple,
    ) -> Optional[tuple]:
        """
        Calculate intersection point of two lines.
        
        Args:
            p1, p2: Points defining first line
            p3, p4: Points defining second line
            
        Returns:
            Intersection point or None if parallel
        """
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if abs(denom) < 1e-10:
            return None  # Lines are parallel
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        
        # Check if intersection is within line segments
        if 0 <= t <= 1:
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            return (int(x), int(y))
        
        return None
    
    def draw_detections(
        self,
        image: np.ndarray,
        detections: dict,
        draw_lines: bool = True,
        draw_contours: bool = True,
        draw_circles: bool = True,
    ) -> np.ndarray:
        """
        Draw detection results on image for visualization.
        
        Args:
            image: Input image
            detections: Detection results dictionary
            draw_lines: Whether to draw lines
            draw_contours: Whether to draw contours
            draw_circles: Whether to draw circles
            
        Returns:
            Image with detections drawn
        """
        output = image.copy()
        
        if len(output.shape) == 2:
            output = cv2.cvtColor(output, cv2.COLOR_GRAY2RGB)
        
        if draw_lines:
            for line in detections.get("lines", []):
                cv2.line(
                    output,
                    line["start"],
                    line["end"],
                    (0, 255, 0),
                    2,
                )
        
        if draw_contours:
            for contour in detections.get("contours", []):
                points = np.array(contour["points"])
                cv2.drawContours(output, [points], -1, (255, 0, 0), 2)
        
        if draw_circles:
            for circle in detections.get("circles", []):
                cv2.circle(
                    output,
                    circle["center"],
                    circle["radius"],
                    (0, 0, 255),
                    2,
                )
        
        return output


