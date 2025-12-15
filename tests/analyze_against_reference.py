#!/usr/bin/env python3
"""
Analyze classification results against manually painted reference.

Compares our automated results with the ground truth reference
and calculates accuracy metrics.
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from collections import defaultdict


# Reference color ranges (BGR format) - based on user's manual classification
# These are approximate ranges to account for anti-aliasing and color variations
REFERENCE_COLORS = {
    "former": {
        "bgr_low": (0, 0, 180),
        "bgr_high": (80, 80, 255),
        "description": "Red - Formers (F1-F7)",
    },
    "fuselage": {
        "bgr_low": (180, 0, 0),
        "bgr_high": (255, 100, 100),
        "description": "Blue - Fuselage/Spars",
    },
    "tail": {
        "bgr_low": (180, 0, 180),
        "bgr_high": (255, 100, 255),
        "description": "Magenta - Tail surfaces",
    },
    "landing_gear": {
        "bgr_low": (180, 150, 200),
        "bgr_high": (255, 200, 255),
        "description": "Pink - Landing gear",
    },
    "motor": {
        "bgr_low": (0, 100, 200),
        "bgr_high": (100, 200, 255),
        "description": "Orange - Motor mount",
    },
    "misc": {
        "bgr_low": (100, 100, 100),
        "bgr_high": (180, 180, 180),
        "description": "Gray - Miscellaneous",
    },
}


def extract_color_mask(img, bgr_low, bgr_high):
    """Extract pixels within a color range."""
    return cv2.inRange(img, np.array(bgr_low), np.array(bgr_high))


def calculate_iou(mask1, mask2):
    """Calculate Intersection over Union between two masks."""
    intersection = np.logical_and(mask1 > 0, mask2 > 0).sum()
    union = np.logical_or(mask1 > 0, mask2 > 0).sum()
    if union == 0:
        return 0.0
    return intersection / union


def calculate_pixel_accuracy(reference_mask, predicted_mask):
    """Calculate pixel-level accuracy."""
    if reference_mask.sum() == 0:
        return 0.0
    correct = np.logical_and(reference_mask > 0, predicted_mask > 0).sum()
    return correct / reference_mask.sum()


def analyze_images():
    """Compare automated results against reference."""
    
    # Load images
    reference_path = Path("samples/pdf_page1_raster_classified_training.png")
    contour_path = Path("output/painted_contours.png")
    vlm_path = Path("output/vlm_classified_components.png")
    
    if not reference_path.exists():
        print(f"[X] Reference not found: {reference_path}")
        return
    
    reference = cv2.imread(str(reference_path))
    
    results = {}
    
    if contour_path.exists():
        results["Local Contour"] = cv2.imread(str(contour_path))
    
    if vlm_path.exists():
        results["AWS Bedrock VLM"] = cv2.imread(str(vlm_path))
    
    improved_path = Path("output/improved_classification.png")
    if improved_path.exists():
        results["Improved (Rules)"] = cv2.imread(str(improved_path))
    
    print("=" * 70)
    print("CLASSIFICATION ACCURACY ANALYSIS")
    print("Reference: samples/pdf_page1_raster_classified_training.png")
    print("=" * 70)
    print()
    
    # Extract reference masks for each category
    print("[1] Extracting reference color masks...")
    reference_masks = {}
    for category, colors in REFERENCE_COLORS.items():
        mask = extract_color_mask(reference, colors["bgr_low"], colors["bgr_high"])
        reference_masks[category] = mask
        pixel_count = mask.sum() // 255
        print(f"    {category}: {pixel_count:,} pixels ({colors['description']})")
    print()
    
    # Analyze each result
    for name, img in results.items():
        print(f"[2] Analyzing: {name}")
        print("-" * 50)
        
        if img is None:
            print("    [X] Failed to load image")
            continue
        
        # Resize if needed
        if img.shape[:2] != reference.shape[:2]:
            img = cv2.resize(img, (reference.shape[1], reference.shape[0]))
        
        total_iou = 0
        total_accuracy = 0
        category_results = []
        
        for category, ref_mask in reference_masks.items():
            colors = REFERENCE_COLORS[category]
            
            # Extract predicted mask
            pred_mask = extract_color_mask(img, colors["bgr_low"], colors["bgr_high"])
            
            # Calculate metrics
            iou = calculate_iou(ref_mask, pred_mask)
            accuracy = calculate_pixel_accuracy(ref_mask, pred_mask)
            
            ref_pixels = ref_mask.sum() // 255
            pred_pixels = pred_mask.sum() // 255
            
            total_iou += iou
            total_accuracy += accuracy
            
            category_results.append({
                "category": category,
                "iou": iou,
                "accuracy": accuracy,
                "ref_pixels": ref_pixels,
                "pred_pixels": pred_pixels,
            })
            
            # Visual indicator
            if iou > 0.5:
                status = "✅"
            elif iou > 0.2:
                status = "⚠️"
            else:
                status = "❌"
            
            print(f"    {status} {category:15} | IoU: {iou:.1%} | Recall: {accuracy:.1%} | "
                  f"Ref: {ref_pixels:,} px | Pred: {pred_pixels:,} px")
        
        avg_iou = total_iou / len(reference_masks)
        avg_accuracy = total_accuracy / len(reference_masks)
        
        print()
        print(f"    OVERALL SCORE:")
        print(f"    Average IoU: {avg_iou:.1%}")
        print(f"    Average Recall: {avg_accuracy:.1%}")
        print()
    
    # Generate improvement suggestions
    print("=" * 70)
    print("IMPROVEMENT RECOMMENDATIONS")
    print("=" * 70)
    print()
    
    print("1. VIEW CONTEXT UNDERSTANDING")
    print("   - Formers appear as LINES in side view, SHAPES in template view")
    print("   - Need to detect and color structural lines (spars, former positions)")
    print()
    
    print("2. LINE DETECTION NEEDED")
    print("   - Add Hough line detection for:")
    print("     * Vertical lines → Former positions (red)")
    print("     * Horizontal lines → Spars (blue)")
    print()
    
    print("3. REGION SEGMENTATION")
    print("   - Main fuselage body should be filled blue")
    print("   - Template pieces (right column) need individual detection")
    print()
    
    print("4. IMPROVED VLM PROMPTS")
    print("   - Explain view context in prompt")
    print("   - Ask for both shapes AND lines")
    print("   - Distinguish assembly view from template views")
    print()
    
    # Save comparison image
    print("Generating comparison image...")
    
    h, w = reference.shape[:2]
    comparison = np.zeros((h, w * 3, 3), dtype=np.uint8)
    
    # Reference
    comparison[:, :w] = reference
    cv2.putText(comparison, "REFERENCE (Ground Truth)", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # Local result
    if "Local Contour" in results and results["Local Contour"] is not None:
        local_img = cv2.resize(results["Local Contour"], (w, h))
        comparison[:, w:w*2] = local_img
        cv2.putText(comparison, "LOCAL CONTOUR", (w + 10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # VLM result
    if "AWS Bedrock VLM" in results and results["AWS Bedrock VLM"] is not None:
        vlm_img = cv2.resize(results["AWS Bedrock VLM"], (w, h))
        comparison[:, w*2:] = vlm_img
        cv2.putText(comparison, "AWS BEDROCK VLM", (w*2 + 10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    comparison_path = Path("output/classification_comparison.png")
    cv2.imwrite(str(comparison_path), comparison)
    print(f"[OK] Saved comparison: {comparison_path}")


if __name__ == "__main__":
    analyze_images()

