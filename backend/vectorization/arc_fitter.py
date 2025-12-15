"""
Arc and circle fitting for vectorization.
"""

import numpy as np
import cv2
from typing import Optional


class ArcFitter:
    """Fits arcs and circles to contours."""
    
    def __init__(
        self,
        circularity_threshold: float = 0.8,
        min_radius: int = 5,
    ):
        self.circularity_threshold = circularity_threshold
        self.min_radius = min_radius
    
    def fit_contours(self, contours: list[dict]) -> list[dict]:
        """Fit arcs/circles to contours where appropriate."""
        results = []
        
        for contour in contours:
            points = np.array(contour["points"], dtype=np.float32)
            
            if len(points) < 5:
                continue
            
            # Try to fit circle
            circle = self._fit_circle(points)
            
            if circle and circle["radius"] >= self.min_radius:
                # Check how well the circle fits
                fit_error = self._circle_fit_error(points, circle)
                
                if fit_error < 0.1:  # Good fit
                    if self._is_full_circle(points, circle):
                        results.append({
                            "type": "circle",
                            "center": circle["center"],
                            "radius": circle["radius"],
                            "fit_error": fit_error,
                        })
                    else:
                        # Partial arc
                        arc = self._fit_arc(points, circle)
                        if arc:
                            results.append(arc)
        
        return results
    
    def _fit_circle(self, points: np.ndarray) -> Optional[dict]:
        """Fit a circle to points using least squares."""
        if len(points) < 3:
            return None
        
        # Reshape for OpenCV
        points = points.reshape(-1, 1, 2).astype(np.float32)
        
        # Fit minimum enclosing circle
        (cx, cy), radius = cv2.minEnclosingCircle(points)
        
        return {
            "center": (float(cx), float(cy)),
            "radius": float(radius),
        }
    
    def _circle_fit_error(self, points: np.ndarray, circle: dict) -> float:
        """Calculate RMS error of circle fit."""
        cx, cy = circle["center"]
        r = circle["radius"]
        
        distances = np.sqrt((points[:, 0] - cx) ** 2 + (points[:, 1] - cy) ** 2)
        errors = np.abs(distances - r)
        
        return float(np.mean(errors) / r) if r > 0 else float('inf')
    
    def _is_full_circle(self, points: np.ndarray, circle: dict) -> bool:
        """Check if points form a full circle."""
        cx, cy = circle["center"]
        
        # Calculate angles of all points
        angles = np.arctan2(points[:, 1] - cy, points[:, 0] - cx)
        angles = np.sort(angles)
        
        # Check for large gaps (> 45 degrees)
        diffs = np.diff(angles)
        max_gap = np.max(diffs) if len(diffs) > 0 else 0
        
        # Also check wrap-around gap
        wrap_gap = 2 * np.pi - (angles[-1] - angles[0]) if len(angles) > 1 else 0
        max_gap = max(max_gap, wrap_gap)
        
        return max_gap < np.pi / 4  # Less than 45 degree gap
    
    def _fit_arc(self, points: np.ndarray, circle: dict) -> Optional[dict]:
        """Fit an arc to points given the circle."""
        cx, cy = circle["center"]
        
        # Calculate angles
        angles = np.arctan2(points[:, 1] - cy, points[:, 0] - cx)
        
        start_angle = float(np.degrees(np.min(angles)))
        end_angle = float(np.degrees(np.max(angles)))
        
        return {
            "type": "arc",
            "center": circle["center"],
            "radius": circle["radius"],
            "start_angle": start_angle,
            "end_angle": end_angle,
        }


