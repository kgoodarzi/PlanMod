#!/usr/bin/env python3
"""Create side-by-side comparison of all classification methods."""

import sys
import cv2
import numpy as np
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def create_comparison():
    """Create 3-way comparison image."""
    
    # Load images
    reference = cv2.imread("samples/pdf_page1_raster_classified_training.png")
    improved = cv2.imread("output/improved_classification.png")
    vlm = cv2.imread("output/vlm_classified_components.png")
    
    if reference is None:
        print("[X] Reference not found")
        return
    
    if improved is None:
        print("[X] Improved not found")
        return
        
    # Get target size from reference
    h, w = reference.shape[:2]
    
    # Resize others to match
    if improved is not None:
        improved = cv2.resize(improved, (w, h))
    
    if vlm is not None:
        vlm = cv2.resize(vlm, (w, h))
    else:
        vlm = np.zeros_like(reference)
    
    # Create comparison
    comparison = np.zeros((h, w * 3 + 40, 3), dtype=np.uint8)
    comparison[:, :, :] = 255  # White background
    
    # Add images
    comparison[:, :w] = reference
    comparison[:, w+20:w*2+20] = improved
    comparison[:, w*2+40:] = vlm
    
    # Add titles
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(comparison, "REFERENCE (Ground Truth)", (10, 30), font, 1.0, (0, 0, 0), 2)
    cv2.putText(comparison, "IMPROVED (Rule-based)", (w + 30, 30), font, 1.0, (0, 0, 0), 2)
    cv2.putText(comparison, "AWS BEDROCK VLM", (w * 2 + 50, 30), font, 1.0, (0, 0, 0), 2)
    
    # Save
    output_path = "output/full_comparison.png"
    cv2.imwrite(output_path, comparison)
    print(f"[OK] Saved: {output_path}")
    
    # Also create a smaller version for easier viewing
    small = cv2.resize(comparison, (comparison.shape[1] // 2, comparison.shape[0] // 2))
    cv2.imwrite("output/full_comparison_small.png", small)
    print(f"[OK] Saved: output/full_comparison_small.png")

if __name__ == "__main__":
    create_comparison()


