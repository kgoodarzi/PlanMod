"""
Line detection for vectorization.
"""

import cv2
import numpy as np


class LineDetector:
    """Detects and extracts lines from images."""
    
    def __init__(
        self,
        canny_low: int = 50,
        canny_high: int = 150,
        hough_threshold: int = 50,
        min_line_length: int = 20,
        max_line_gap: int = 10,
    ):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
    
    def detect(self, gray: np.ndarray) -> list[dict]:
        """Detect lines in grayscale image."""
        # Edge detection
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)
        
        # Hough transform
        lines_p = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=self.hough_threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap,
        )
        
        lines = []
        if lines_p is not None:
            for line in lines_p:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                
                lines.append({
                    "start": (int(x1), int(y1)),
                    "end": (int(x2), int(y2)),
                    "length": float(length),
                    "angle": float(angle),
                })
        
        # Merge collinear lines
        lines = self._merge_collinear(lines)
        
        return lines
    
    def _merge_collinear(
        self,
        lines: list[dict],
        angle_tolerance: float = 2.0,
        distance_tolerance: float = 10.0,
    ) -> list[dict]:
        """Merge nearly collinear line segments."""
        if len(lines) < 2:
            return lines
        
        merged = []
        used = set()
        
        for i, line1 in enumerate(lines):
            if i in used:
                continue
            
            current = line1.copy()
            
            for j, line2 in enumerate(lines[i + 1:], i + 1):
                if j in used:
                    continue
                
                # Check if angles are similar
                angle_diff = abs(current["angle"] - line2["angle"])
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff
                
                if angle_diff > angle_tolerance:
                    continue
                
                # Check if lines are close
                dist = self._point_line_distance(
                    line2["start"],
                    current["start"],
                    current["end"],
                )
                
                if dist > distance_tolerance:
                    continue
                
                # Merge lines
                points = [
                    current["start"],
                    current["end"],
                    line2["start"],
                    line2["end"],
                ]
                
                # Find extreme points along the line direction
                if abs(current["angle"]) < 45 or abs(current["angle"]) > 135:
                    # Mostly horizontal
                    points.sort(key=lambda p: p[0])
                else:
                    # Mostly vertical
                    points.sort(key=lambda p: p[1])
                
                current["start"] = points[0]
                current["end"] = points[-1]
                current["length"] = np.sqrt(
                    (current["end"][0] - current["start"][0]) ** 2 +
                    (current["end"][1] - current["start"][1]) ** 2
                )
                
                used.add(j)
            
            merged.append(current)
            used.add(i)
        
        return merged
    
    def _point_line_distance(
        self,
        point: tuple,
        line_start: tuple,
        line_end: tuple,
    ) -> float:
        """Calculate distance from point to line segment."""
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        
        return np.sqrt((px - nearest_x) ** 2 + (py - nearest_y) ** 2)


