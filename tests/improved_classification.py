#!/usr/bin/env python3
"""
Improved classification based on expert reference analysis.

Uses domain knowledge rules from plan_classification_rules.py
to properly identify components in different view contexts.
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


# =============================================================================
# COMPONENT DEFINITIONS BASED ON REFERENCE ANALYSIS
# =============================================================================

# Components are defined with their VIEW CONTEXT
# Format: (id, category, geometry_type, view, x%, y%, w%, h%)

COMPONENTS = [
    # === SIDE VIEW COMPONENTS ===
    
    # Fuselage sides (FS1, FS2, FS3) - BLUE SURFACES in side view (reinforced)
    ("FS1-side", "fuselage_side", "shape", "side_view", 5, 60, 50, 32),
    ("FS2-side", "fuselage_side", "shape", "side_view", 30, 25, 20, 15),
    ("FS3-side", "fuselage_side", "shape", "side_view", 35, 20, 15, 12),
    
    # Formers as LINES in side view (vertical cuts) - RED
    ("F1-line", "former", "line", "side_view", 35, 78, 2, 15),
    ("F2-line", "former", "line", "side_view", 40, 75, 2, 12),
    ("F3-line", "former", "line", "side_view", 47, 72, 2, 10),
    ("F4-line", "former", "line", "side_view", 50, 70, 2, 10),
    ("F5-line", "former", "line", "side_view", 28, 65, 2, 12),
    ("F5A-line", "former", "line", "side_view", 30, 62, 2, 10),
    ("F6-line", "former", "line", "side_view", 42, 68, 2, 8),
    ("F7-line", "former", "line", "side_view", 48, 58, 2, 8),
    
    # Spars as LINES (horizontal/curved) - BLUE
    ("spar-top", "spar", "line", "side_view", 5, 62, 50, 2),
    ("spar-bottom", "spar", "line", "side_view", 5, 78, 50, 2),
    ("spar-mid", "spar", "line", "side_view", 15, 70, 35, 2),
    
    # Landing gear in side view - PINK
    ("UC-wheel", "landing_gear", "shape", "side_view", 3, 76, 6, 8),
    ("UC-leg", "landing_gear", "line", "side_view", 5, 72, 3, 10),
    ("UC-wire", "landing_gear", "line", "side_view", 55, 70, 15, 8),
    
    # Motor at nose - ORANGE
    ("M-nose", "motor", "shape", "side_view", 2, 78, 8, 14),
    
    # Nose block - GRAY
    ("nose-block", "misc", "shape", "side_view", 2, 85, 6, 8),
    
    # Wing former (top of fuselage) - BLUE
    ("wing-center", "fuselage_side", "shape", "side_view", 20, 58, 25, 6),
    
    # === TEMPLATE VIEW COMPONENTS (right column) ===
    
    # Former templates - RED SHAPES
    ("F3-template", "former", "shape", "template", 78, 82, 10, 8),
    ("F4-template", "former", "shape", "template", 88, 72, 8, 8),
    ("F6-template", "former", "shape", "template", 88, 62, 7, 8),
    ("F7-template", "former", "shape", "template", 82, 52, 12, 10),
    
    # Fuselage side template - BLUE SHAPE
    ("FS1-template", "fuselage_side", "shape", "template", 86, 65, 12, 28),
    
    # Landing gear template - PINK SHAPE
    ("UC-template", "landing_gear", "shape", "template", 88, 78, 8, 6),
    
    # Misc templates - GRAY
    ("B-template", "misc", "shape", "template", 92, 86, 6, 6),
    ("M-template", "motor", "shape", "template", 72, 85, 6, 6),
    
    # === TOP VIEW / TAIL AREA ===
    
    # Tail stabilizer plan - MAGENTA
    ("TS-plan", "tail", "shape", "top_view", 1, 1, 12, 24),
    ("T1-template", "tail", "shape", "template", 24, 3, 10, 8),
    ("T2-template", "tail", "shape", "template", 32, 1, 14, 12),
    
    # Additional fuselage side templates at top
    ("FS2-template", "fuselage_side", "shape", "template", 58, 2, 16, 14),
    ("FS3-template", "fuselage_side", "shape", "template", 10, 3, 12, 8),
]

# Category colors (BGR for OpenCV)
CATEGORY_COLORS_BGR = {
    "former": (0, 0, 255),           # Red
    "fuselage_side": (255, 0, 0),    # Blue
    "spar": (255, 0, 0),             # Blue
    "tail": (255, 0, 255),           # Magenta
    "landing_gear": (200, 180, 255), # Pink
    "motor": (0, 165, 255),          # Orange
    "wing": (0, 255, 0),             # Green
    "misc": (128, 128, 128),         # Gray
}


def detect_structural_lines(img):
    """
    Detect structural lines using Hough transform.
    Returns classified lines as former positions or spars.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Detect lines
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                            minLineLength=30, maxLineGap=10)
    
    former_lines = []  # Vertical
    spar_lines = []    # Horizontal
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            
            if length < 20:
                continue
            
            # Calculate angle
            angle = np.arctan2(y2-y1, x2-x1) * 180 / np.pi
            
            # Vertical lines (formers) - within 20° of vertical
            if 70 < abs(angle) < 110:
                former_lines.append((x1, y1, x2, y2))
            
            # Horizontal lines (spars) - within 20° of horizontal
            elif abs(angle) < 20 or abs(angle) > 160:
                spar_lines.append((x1, y1, x2, y2))
    
    return former_lines, spar_lines


def paint_improved():
    """Create improved classification based on reference analysis."""
    
    img_path = Path("output/pdf_page1_raster.png")
    if not img_path.exists():
        # Generate it first
        from backend.ingest.pdf_processor import PDFProcessor
        pdf_path = Path("samples/Aeronca_Defender_Plan_Vector.pdf")
        pdf_data = pdf_path.read_bytes()
        processor = PDFProcessor(dpi=150)
        images = processor.rasterize(pdf_data, dpi=150, pages=[0])
        img = images[0]
        cv2.imwrite(str(img_path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    
    img = cv2.imread(str(img_path))
    if img is None:
        print("[X] Failed to load image")
        return False
    
    h, w = img.shape[:2]
    print(f"[*] Image: {w}x{h} pixels")
    
    # Create output layers
    result = img.copy()
    overlay = np.zeros_like(img)
    
    # Track statistics
    stats = {}
    
    # 1. Paint defined components
    print("\n[1] Painting defined components...")
    for comp_id, category, geom_type, view, x_pct, y_pct, w_pct, h_pct in COMPONENTS:
        x = int(x_pct / 100 * w)
        y = int(y_pct / 100 * h)
        bw = int(w_pct / 100 * w)
        bh = int(h_pct / 100 * h)
        
        color = CATEGORY_COLORS_BGR.get(category, (128, 128, 128))
        
        if geom_type == "shape":
            # Fill the region
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, -1)
            
            # Try flood fill for better shape detection
            cx, cy = x + bw // 2, y + bh // 2
            if 0 <= cx < w and 0 <= cy < h:
                pixel = img[cy, cx]
                if np.mean(pixel) > 200:  # Light area
                    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
                    cv2.floodFill(overlay, ff_mask, (cx, cy), color,
                                  loDiff=(30, 30, 30), upDiff=(30, 30, 30),
                                  flags=cv2.FLOODFILL_FIXED_RANGE)
        
        elif geom_type == "line":
            # Draw thick line
            if bw > bh:  # Horizontal
                cv2.line(overlay, (x, y + bh//2), (x + bw, y + bh//2), color, 3)
            else:  # Vertical
                cv2.line(overlay, (x + bw//2, y), (x + bw//2, y + bh), color, 3)
        
        stats[category] = stats.get(category, 0) + 1
    
    # 2. Detect and paint structural lines
    print("[2] Detecting structural lines...")
    former_lines, spar_lines = detect_structural_lines(img)
    
    # Filter lines to side view region only (left 60% of image, middle height)
    side_view_region = (0, int(h * 0.5), int(w * 0.6), int(h * 0.45))
    
    former_count = 0
    spar_count = 0
    
    for x1, y1, x2, y2 in former_lines:
        # Check if line is in side view region
        if (side_view_region[0] <= x1 <= side_view_region[0] + side_view_region[2] and
            side_view_region[1] <= y1 <= side_view_region[1] + side_view_region[3]):
            cv2.line(overlay, (x1, y1), (x2, y2), CATEGORY_COLORS_BGR["former"], 2)
            former_count += 1
    
    for x1, y1, x2, y2 in spar_lines:
        if (side_view_region[0] <= x1 <= side_view_region[0] + side_view_region[2] and
            side_view_region[1] <= y1 <= side_view_region[1] + side_view_region[3]):
            cv2.line(overlay, (x1, y1), (x2, y2), CATEGORY_COLORS_BGR["spar"], 2)
            spar_count += 1
    
    print(f"    Former lines detected: {former_count}")
    print(f"    Spar lines detected: {spar_count}")
    
    # 3. Blend overlay with original
    alpha = 0.5
    result = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
    
    # Keep black lines visible
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, black_mask = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    result[black_mask > 0] = img[black_mask > 0]
    
    # 4. Add legend
    legend_y = 30
    legend_x = 20
    cv2.rectangle(result, (10, 10), (200, 200), (255, 255, 255), -1)
    cv2.rectangle(result, (10, 10), (200, 200), (0, 0, 0), 2)
    
    cv2.putText(result, "COMPONENT LEGEND", (legend_x, legend_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    legend_y += 22
    
    for category, color in CATEGORY_COLORS_BGR.items():
        count = stats.get(category, 0)
        cv2.rectangle(result, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 3), color, -1)
        cv2.rectangle(result, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 3), (0, 0, 0), 1)
        cv2.putText(result, f"{category} ({count})", (legend_x + 25, legend_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
        legend_y += 18
    
    # Save result
    output_path = Path("output/improved_classification.png")
    cv2.imwrite(str(output_path), result)
    print(f"\n[OK] Saved: {output_path}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("CLASSIFICATION SUMMARY")
    print("=" * 50)
    for cat, count in sorted(stats.items()):
        print(f"  {cat}: {count}")
    print(f"\nTotal components: {sum(stats.values())}")
    print(f"Former lines: {former_count}")
    print(f"Spar lines: {spar_count}")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Improved Classification with Domain Rules")
    print("=" * 60)
    paint_improved()


