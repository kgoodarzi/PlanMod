"""
Contour tracing for vectorization.
"""

import cv2
import numpy as np


class ContourTracer:
    """Traces contours and converts to polylines."""
    
    def __init__(
        self,
        min_area: int = 50,
        epsilon_factor: float = 0.01,
    ):
        self.min_area = min_area
        self.epsilon_factor = epsilon_factor
    
    def trace(self, gray: np.ndarray) -> list[dict]:
        """Trace contours in image."""
        # Threshold
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, hierarchy = cv2.findContours(
            binary,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        
        results = []
        
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            if area < self.min_area:
                continue
            
            # Simplify contour
            perimeter = cv2.arcLength(contour, closed=True)
            epsilon = self.epsilon_factor * perimeter
            approx = cv2.approxPolyDP(contour, epsilon, closed=True)
            
            # Check if closed
            is_closed = cv2.isContourConvex(approx) or area > 0
            
            # Convert points
            points = [(int(p[0][0]), int(p[0][1])) for p in approx]
            
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            results.append({
                "points": points,
                "is_closed": is_closed,
                "area": float(area),
                "perimeter": float(perimeter),
                "bounds": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                "hierarchy_idx": i,
            })
        
        return results


