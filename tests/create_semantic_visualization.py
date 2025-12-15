#!/usr/bin/env python3
"""
Create semantic visualization with proper component bounding boxes.
Based on VLM analysis of the Aeronca Defender plan.
"""

import sys
import os
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from PIL import Image


# Component locations identified by VLM analysis (approximate % of image)
# Format: {"id": ..., "x_pct": left%, "y_pct": top%, "w_pct": width%, "h_pct": height%, "category": ...}
COMPONENTS = [
    # Formers - Red
    {"id": "F1", "x_pct": 28, "y_pct": 78, "w_pct": 8, "h_pct": 12, "category": "formers"},
    {"id": "F2", "x_pct": 38, "y_pct": 82, "w_pct": 4, "h_pct": 8, "category": "formers"},
    {"id": "F3", "x_pct": 56, "y_pct": 76, "w_pct": 3, "h_pct": 6, "category": "formers"},
    {"id": "F4", "x_pct": 52, "y_pct": 71, "w_pct": 4, "h_pct": 5, "category": "formers"},
    {"id": "F5", "x_pct": 30, "y_pct": 68, "w_pct": 5, "h_pct": 8, "category": "formers"},
    {"id": "F5A", "x_pct": 24, "y_pct": 62, "w_pct": 8, "h_pct": 8, "category": "formers"},
    {"id": "F6", "x_pct": 43, "y_pct": 69, "w_pct": 3, "h_pct": 6, "category": "formers"},
    {"id": "F7", "x_pct": 47, "y_pct": 58, "w_pct": 8, "h_pct": 8, "category": "formers"},
    
    # Tail surfaces - Magenta
    {"id": "TS", "x_pct": 2, "y_pct": 2, "w_pct": 8, "h_pct": 20, "category": "tail_surfaces"},
    {"id": "T1", "x_pct": 32, "y_pct": 8, "w_pct": 5, "h_pct": 6, "category": "tail_surfaces"},
    {"id": "T2", "x_pct": 35, "y_pct": 2, "w_pct": 8, "h_pct": 10, "category": "tail_surfaces"},
    
    # Fuselage sides - Blue
    {"id": "FS1", "x_pct": 85, "y_pct": 72, "w_pct": 12, "h_pct": 20, "category": "fuselage_sides"},
    {"id": "FS2", "x_pct": 60, "y_pct": 2, "w_pct": 12, "h_pct": 10, "category": "fuselage_sides"},
    {"id": "FS3", "x_pct": 12, "y_pct": 2, "w_pct": 10, "h_pct": 8, "category": "fuselage_sides"},
    
    # Landing gear - Pink
    {"id": "UC", "x_pct": 60, "y_pct": 68, "w_pct": 5, "h_pct": 8, "category": "landing_gear"},
    {"id": "u/c legs", "x_pct": 65, "y_pct": 68, "w_pct": 10, "h_pct": 10, "category": "landing_gear"},
    
    # Motor mount - Orange
    {"id": "M", "x_pct": 2, "y_pct": 78, "w_pct": 10, "h_pct": 15, "category": "motor_mount"},
    
    # Wing - Green
    {"id": "spar area", "x_pct": 82, "y_pct": 52, "w_pct": 12, "h_pct": 8, "category": "wing"},
    
    # Miscellaneous - Gray
    {"id": "B", "x_pct": 88, "y_pct": 78, "w_pct": 8, "h_pct": 10, "category": "miscellaneous"},
    {"id": "horn", "x_pct": 42, "y_pct": 30, "w_pct": 5, "h_pct": 8, "category": "miscellaneous"},
    
    # Title block
    {"id": "Aeronca Defender", "x_pct": 18, "y_pct": 46, "w_pct": 22, "h_pct": 8, "category": "title"},
]

# Category colors (BGR for OpenCV)
CATEGORY_COLORS = {
    "formers": (0, 0, 200),         # Red
    "tail_surfaces": (200, 0, 200),  # Magenta
    "fuselage_sides": (200, 100, 0), # Blue
    "landing_gear": (100, 100, 200), # Pink
    "motor_mount": (50, 150, 255),   # Orange
    "wing": (0, 200, 0),             # Green
    "miscellaneous": (150, 150, 150),# Gray
    "title": (100, 50, 50),          # Dark blue
}


def create_visualization():
    """Create semantic visualization with labeled bounding boxes."""
    
    # Load image
    img_path = Path("output/pdf_page1_raster.png")
    if not img_path.exists():
        print(f"[X] Image not found: {img_path}")
        return False
    
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"[X] Failed to load image")
        return False
    
    height, width = img.shape[:2]
    print(f"[*] Image size: {width}x{height}")
    
    # Create overlay
    overlay = img.copy()
    
    # Draw component boxes
    for comp in COMPONENTS:
        x = int(comp["x_pct"] / 100 * width)
        y = int(comp["y_pct"] / 100 * height)
        w = int(comp["w_pct"] / 100 * width)
        h = int(comp["h_pct"] / 100 * height)
        
        color = CATEGORY_COLORS.get(comp["category"], (128, 128, 128))
        
        # Draw filled rectangle with transparency
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        
        # Draw border
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        
        # Draw label
        label = comp["id"]
        font_scale = 0.5
        thickness = 1
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        
        # Label background
        cv2.rectangle(img, (x, y - text_h - 6), (x + text_w + 4, y), color, -1)
        cv2.putText(img, label, (x + 2, y - 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
    
    # Blend overlay
    alpha = 0.25
    result = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
    
    # Add legend
    legend_width = 220
    legend_x = 20
    legend_y = 30
    
    # Legend background
    cv2.rectangle(result, (legend_x - 10, legend_y - 25), (legend_x + legend_width, legend_y + len(CATEGORY_COLORS) * 25 + 10), (255, 255, 255), -1)
    cv2.rectangle(result, (legend_x - 10, legend_y - 25), (legend_x + legend_width, legend_y + len(CATEGORY_COLORS) * 25 + 10), (0, 0, 0), 2)
    
    cv2.putText(result, "COMPONENT LEGEND", (legend_x, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    legend_y += 25
    
    category_counts = {}
    for comp in COMPONENTS:
        cat = comp["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    for category, color in CATEGORY_COLORS.items():
        count = category_counts.get(category, 0)
        if count == 0:
            continue
            
        # Color box
        cv2.rectangle(result, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 4), color, -1)
        cv2.rectangle(result, (legend_x, legend_y - 12), (legend_x + 18, legend_y + 4), (0, 0, 0), 1)
        
        # Label
        label = f"{category.replace('_', ' ').title()} ({count})"
        cv2.putText(result, label, (legend_x + 25, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        legend_y += 22
    
    # Save result
    output_path = Path("output/pdf_semantic_visualization.png")
    cv2.imwrite(str(output_path), result)
    print(f"[OK] Saved: {output_path}")
    
    # Also create a simpler version showing just outlines
    img_outline = cv2.imread(str(img_path))
    for comp in COMPONENTS:
        x = int(comp["x_pct"] / 100 * width)
        y = int(comp["y_pct"] / 100 * height)
        w = int(comp["w_pct"] / 100 * width)
        h = int(comp["h_pct"] / 100 * height)
        
        color = CATEGORY_COLORS.get(comp["category"], (128, 128, 128))
        cv2.rectangle(img_outline, (x, y), (x + w, y + h), color, 3)
        
        label = comp["id"]
        cv2.putText(img_outline, label, (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    outline_path = Path("output/pdf_component_outlines.png")
    cv2.imwrite(str(outline_path), img_outline)
    print(f"[OK] Saved: {outline_path}")
    
    return True


def print_summary():
    """Print component summary."""
    print()
    print("=" * 60)
    print("COMPONENT CLASSIFICATION SUMMARY")
    print("=" * 60)
    
    by_category = {}
    for comp in COMPONENTS:
        cat = comp["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(comp["id"])
    
    total = 0
    for category, items in sorted(by_category.items()):
        color_rgb = tuple(reversed(CATEGORY_COLORS.get(category, (128, 128, 128))))
        print(f"\n  [{category.upper()}] - RGB{color_rgb}")
        print(f"    Components: {', '.join(items)}")
        print(f"    Count: {len(items)}")
        total += len(items)
    
    print()
    print(f"  TOTAL: {total} components identified")
    print("=" * 60)


if __name__ == "__main__":
    print("Creating semantic visualization...")
    success = create_visualization()
    if success:
        print_summary()
    sys.exit(0 if success else 1)


