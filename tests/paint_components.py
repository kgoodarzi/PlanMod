#!/usr/bin/env python3
"""
Paint components identified by VLM analysis.

Fills each component shape with its category color using flood fill,
rather than drawing bounding boxes.
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from PIL import Image

# Component regions identified by Claude VLM analysis
# Format: (name, category, x%, y%, w%, h%) - percentages of image dimensions
# These are approximate regions containing each component's closed shape

COMPONENTS = [
    # === FORMERS (Red) ===
    # Main fuselage profile formers visible in drawing
    ("F1", "former", 36, 85, 12, 12),       # Nose former with hatching
    ("F2", "former", 33, 82, 6, 8),         # Forward former
    ("F3", "former", 45, 78, 4, 6),         # Mid former  
    ("F4", "former", 48, 73, 5, 6),         # Rear cockpit former
    ("F5", "former", 15, 64, 10, 12),       # Wing saddle former (large)
    ("F5A", "former", 20, 62, 6, 8),        # Dihedral brace
    ("F6", "former", 40, 69, 4, 5),         # Small curved former
    ("F7", "former", 40, 56, 10, 8),        # Tail mount former
    # Template pieces on right
    ("F3 ply", "former", 78, 81, 8, 8),     # F3 template
    ("F4 ply", "former", 88, 72, 8, 8),     # F4 template  
    ("F6 ply", "former", 88, 64, 7, 7),     # F6 template
    ("F7 ply", "former", 82, 54, 10, 8),    # F7 template
    
    # === TAIL SURFACES (Magenta) ===
    ("TS", "tail", 1, 1, 10, 22),           # Full tail stabilizer outline
    ("T1", "tail", 24, 5, 8, 6),            # T1 rib
    ("T2", "tail", 32, 2, 12, 10),          # T2 rib with horn
    ("TS-small", "tail", 1, 22, 6, 8),      # Small TS piece
    
    # === FUSELAGE SIDES (Blue) ===
    ("FS1", "fuselage", 85, 65, 12, 28),    # Main fuselage side panel
    ("FS2", "fuselage", 60, 2, 14, 12),     # FS2 top
    ("FS3", "fuselage", 10, 3, 10, 8),      # FS3 top-left
    ("Fuselage profile", "fuselage", 2, 60, 55, 32), # Main side profile
    
    # === LANDING GEAR (Pink) ===
    ("UC-1", "landing_gear", 2, 70, 6, 10), # UC left
    ("UC-2", "landing_gear", 55, 73, 5, 6), # UC center
    ("UC-3", "landing_gear", 72, 83, 6, 8), # UC bottom-right
    ("UC ply", "landing_gear", 88, 75, 6, 7), # UC template
    
    # === MOTOR (Orange) ===
    ("M", "motor", 2, 80, 10, 12),          # Motor mount with cylinders
    
    # === MISCELLANEOUS (Gray) ===
    ("B", "misc", 56, 73, 4, 5),            # Bottom piece
    ("B ply", "misc", 92, 85, 6, 6),        # B template
    ("horn", "misc", 42, 27, 4, 5),         # Control horn
]

# Category colors (BGR for OpenCV)
CATEGORY_COLORS = {
    "former": (0, 0, 255),         # Red
    "tail": (255, 0, 255),         # Magenta  
    "fuselage": (255, 100, 0),     # Blue
    "landing_gear": (180, 150, 255), # Pink
    "motor": (0, 165, 255),        # Orange
    "misc": (128, 128, 128),       # Gray
    "wing": (0, 255, 0),           # Green
}

CATEGORY_COLORS_RGB = {
    "former": (255, 0, 0),         # Red
    "tail": (255, 0, 255),         # Magenta  
    "fuselage": (0, 100, 255),     # Blue
    "landing_gear": (255, 150, 180), # Pink
    "motor": (255, 165, 0),        # Orange
    "misc": (128, 128, 128),       # Gray
    "wing": (0, 255, 0),           # Green
}


def flood_fill_component(img, mask, x, y, color, tolerance=30):
    """
    Flood fill a component starting from (x, y).
    Only fills white/light areas (the paper background inside shapes).
    """
    h, w = img.shape[:2]
    
    # Create a mask for flood fill (needs to be 2 pixels larger)
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    
    # Get the seed color
    seed_color = img[y, x]
    
    # Only fill if it's a light color (paper/white area)
    if np.mean(seed_color) < 200:
        return False
    
    # Flood fill
    cv2.floodFill(
        img, ff_mask, (x, y), color,
        loDiff=(tolerance, tolerance, tolerance),
        upDiff=(tolerance, tolerance, tolerance),
        flags=cv2.FLOODFILL_FIXED_RANGE
    )
    
    return True


def find_fill_point(img, x, y, w, h):
    """
    Find a good point to start flood fill within a region.
    Looks for white/light pixels that are inside a closed shape.
    """
    region = img[y:y+h, x:x+w]
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    
    # Find white/light areas
    _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
    
    # Find contours in the region
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        # Just use center
        return x + w // 2, y + h // 2
    
    # Find largest contour and its centroid
    largest = max(contours, key=cv2.contourArea)
    M = cv2.moments(largest)
    if M["m00"] > 0:
        cx = int(M["m10"] / M["m00"]) + x
        cy = int(M["m01"] / M["m00"]) + y
        return cx, cy
    
    return x + w // 2, y + h // 2


def paint_components():
    """Paint each component with its category color."""
    
    # Load image
    img_path = Path("output/pdf_page1_raster.png")
    if not img_path.exists():
        print(f"[X] Image not found: {img_path}")
        return False
    
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"[X] Failed to load image")
        return False
    
    h, w = img.shape[:2]
    print(f"[*] Image size: {w}x{h}")
    
    # Create output image - start with original
    painted = img.copy()
    
    # Create a separate overlay for transparency blending
    overlay = img.copy()
    
    # Track statistics
    filled_count = 0
    category_counts = {}
    
    print(f"[*] Painting {len(COMPONENTS)} components...")
    
    for name, category, x_pct, y_pct, w_pct, h_pct in COMPONENTS:
        # Convert percentages to pixels
        x = int(x_pct / 100 * w)
        y = int(y_pct / 100 * h)
        bw = int(w_pct / 100 * w)
        bh = int(h_pct / 100 * h)
        
        color = CATEGORY_COLORS.get(category, (128, 128, 128))
        
        # Find center point for flood fill
        cx, cy = find_fill_point(img, x, y, bw, bh)
        
        # Try to flood fill from center
        try:
            # Check if point is within bounds
            if 0 <= cx < w and 0 <= cy < h:
                # Check pixel brightness
                pixel = img[cy, cx]
                if np.mean(pixel) > 200:  # Light area
                    # Create mask for this fill
                    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
                    
                    # Flood fill on overlay
                    cv2.floodFill(
                        overlay, ff_mask, (cx, cy), color,
                        loDiff=(25, 25, 25),
                        upDiff=(25, 25, 25),
                        flags=cv2.FLOODFILL_FIXED_RANGE
                    )
                    filled_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1
        except Exception as e:
            print(f"    [!] Failed to fill {name}: {e}")
    
    # Blend overlay with original (semi-transparent fill)
    alpha = 0.5
    painted = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
    
    # Re-draw the black lines on top so they're visible
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, lines_mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    painted[lines_mask > 0] = img[lines_mask > 0]
    
    # Add legend
    legend_y = 30
    legend_x = 20
    cv2.rectangle(painted, (10, 10), (200, 10 + len(CATEGORY_COLORS) * 25 + 30), (255, 255, 255), -1)
    cv2.rectangle(painted, (10, 10), (200, 10 + len(CATEGORY_COLORS) * 25 + 30), (0, 0, 0), 2)
    
    cv2.putText(painted, "COMPONENT LEGEND", (legend_x, legend_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    legend_y += 25
    
    for category, color in CATEGORY_COLORS.items():
        count = category_counts.get(category, 0)
        cv2.rectangle(painted, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 3), color, -1)
        cv2.rectangle(painted, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 3), (0, 0, 0), 1)
        
        label = f"{category} ({count})"
        cv2.putText(painted, label, (legend_x + 25, legend_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        legend_y += 22
    
    # Save result
    output_path = Path("output/painted_components.png")
    cv2.imwrite(str(output_path), painted)
    print(f"[OK] Saved: {output_path}")
    
    print(f"\n[*] Statistics:")
    print(f"    Components filled: {filled_count}/{len(COMPONENTS)}")
    for cat, count in sorted(category_counts.items()):
        print(f"    {cat}: {count}")
    
    return True


def paint_with_contour_detection():
    """
    Alternative approach: detect closed contours and fill them based on proximity
    to known component locations.
    """
    img_path = Path("output/pdf_page1_raster.png")
    img = cv2.imread(str(img_path))
    if img is None:
        return False
    
    h, w = img.shape[:2]
    print(f"[*] Contour-based painting on {w}x{h} image...")
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold to get binary image
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    
    # Find all contours
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"    Found {len(contours)} contours")
    
    # Create colored output
    painted = img.copy()
    
    # Filter and color contours
    filled_count = 0
    category_counts = {}
    
    for contour in contours:
        area = cv2.contourArea(contour)
        
        # Filter by area (ignore very small and very large)
        if area < 500 or area > w * h * 0.3:
            continue
        
        # Get bounding box
        bx, by, bw, bh = cv2.boundingRect(contour)
        
        # Find which component this contour belongs to
        best_match = None
        best_dist = float('inf')
        
        for name, category, x_pct, y_pct, w_pct, h_pct in COMPONENTS:
            cx = int(x_pct / 100 * w) + int(w_pct / 100 * w) // 2
            cy = int(y_pct / 100 * h) + int(h_pct / 100 * h) // 2
            
            # Check if contour center is near component center
            contour_cx = bx + bw // 2
            contour_cy = by + bh // 2
            
            dist = ((cx - contour_cx) ** 2 + (cy - contour_cy) ** 2) ** 0.5
            
            # Check if contour is within component region
            comp_x = int(x_pct / 100 * w)
            comp_y = int(y_pct / 100 * h)
            comp_w = int(w_pct / 100 * w)
            comp_h = int(h_pct / 100 * h)
            
            if (comp_x <= contour_cx <= comp_x + comp_w and
                comp_y <= contour_cy <= comp_y + comp_h):
                if dist < best_dist:
                    best_dist = dist
                    best_match = (name, category)
        
        if best_match:
            name, category = best_match
            color = CATEGORY_COLORS.get(category, (128, 128, 128))
            
            # Fill the contour
            cv2.drawContours(painted, [contour], -1, color, -1)
            filled_count += 1
            category_counts[category] = category_counts.get(category, 0) + 1
    
    # Blend with original to keep lines visible
    alpha = 0.4
    result = cv2.addWeighted(painted, alpha, img, 1 - alpha, 0)
    
    # Re-draw black lines
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, lines_mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    result[lines_mask > 0] = (0, 0, 0)
    
    # Add legend
    legend_y = 30
    legend_x = 20
    cv2.rectangle(result, (10, 10), (220, 10 + len(CATEGORY_COLORS) * 25 + 30), (255, 255, 255), -1)
    cv2.rectangle(result, (10, 10), (220, 10 + len(CATEGORY_COLORS) * 25 + 30), (0, 0, 0), 2)
    
    cv2.putText(result, "COMPONENT LEGEND", (legend_x, legend_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    legend_y += 25
    
    for category, color in CATEGORY_COLORS.items():
        count = category_counts.get(category, 0)
        cv2.rectangle(result, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 3), color, -1)
        cv2.rectangle(result, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 3), (0, 0, 0), 1)
        
        label = f"{category} ({count})"
        cv2.putText(result, label, (legend_x + 25, legend_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        legend_y += 22
    
    output_path = Path("output/painted_contours.png")
    cv2.imwrite(str(output_path), result)
    print(f"[OK] Saved: {output_path}")
    print(f"    Contours matched: {filled_count}")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Component Painting (Fill-based visualization)")
    print("=" * 60)
    print()
    
    # Method 1: Flood fill approach
    print("[1] Flood fill method:")
    paint_components()
    print()
    
    # Method 2: Contour detection approach
    print("[2] Contour detection method:")
    paint_with_contour_detection()
    print()
    
    print("Generated files:")
    print("  - output/painted_components.png (flood fill)")
    print("  - output/painted_contours.png (contour detection)")


