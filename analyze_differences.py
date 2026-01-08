"""
Analyze differences between manual and automated cleaning to improve the algorithm.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def analyze_differences(original_path, manual_path, auto_path):
    """Compare manual vs automated cleaning to identify improvements needed."""
    
    # Read images
    original = cv2.imread(str(original_path))
    manual = cv2.imread(str(manual_path))
    auto = cv2.imread(str(auto_path))
    
    if any(img is None for img in [original, manual, auto]):
        print("Error: Could not read one or more images")
        return
    
    # Convert to grayscale for analysis
    orig_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    manual_gray = cv2.cvtColor(manual, cv2.COLOR_BGR2GRAY)
    auto_gray = cv2.cvtColor(auto, cv2.COLOR_BGR2GRAY)
    
    # Find what was removed in manual vs auto
    # Manual removal: difference between original and manual
    manual_removed = cv2.absdiff(orig_gray, manual_gray)
    _, manual_removed_binary = cv2.threshold(manual_removed, 30, 255, cv2.THRESH_BINARY)
    
    # Auto removal: difference between original and auto
    auto_removed = cv2.absdiff(orig_gray, auto_gray)
    _, auto_removed_binary = cv2.threshold(auto_removed, 30, 255, cv2.THRESH_BINARY)
    
    # What manual removed but auto didn't (missed items)
    missed = cv2.bitwise_and(manual_removed_binary, cv2.bitwise_not(auto_removed_binary))
    
    # What auto removed but manual didn't (over-removed items)
    over_removed = cv2.bitwise_and(auto_removed_binary, cv2.bitwise_not(manual_removed_binary))
    
    # Statistics
    manual_pixels = np.sum(manual_removed_binary > 0)
    auto_pixels = np.sum(auto_removed_binary > 0)
    missed_pixels = np.sum(missed > 0)
    over_removed_pixels = np.sum(over_removed > 0)
    
    print(f"\n=== Analysis Results ===")
    print(f"Manual removed: {manual_pixels} pixels")
    print(f"Auto removed: {auto_pixels} pixels")
    print(f"Missed (manual removed but auto didn't): {missed_pixels} pixels")
    print(f"Over-removed (auto removed but manual didn't): {over_removed_pixels} pixels")
    
    # Create visualization
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # Row 1: Original, Manual, Auto
    axes[0, 0].imshow(cv2.cvtColor(original, cv2.COLOR_BGR2RGB))
    axes[0, 0].set_title('Original', fontsize=12, fontweight='bold')
    axes[0, 0].axis('off')
    
    axes[0, 1].imshow(cv2.cvtColor(manual, cv2.COLOR_BGR2RGB))
    axes[0, 1].set_title('Manual Cleaning (Target)', fontsize=12, fontweight='bold')
    axes[0, 1].axis('off')
    
    axes[0, 2].imshow(cv2.cvtColor(auto, cv2.COLOR_BGR2RGB))
    axes[0, 2].set_title('Auto Cleaning (Current)', fontsize=12, fontweight='bold')
    axes[0, 2].axis('off')
    
    # Row 2: What was removed
    axes[1, 0].imshow(manual_removed_binary, cmap='hot')
    axes[1, 0].set_title(f'Manual Removed ({manual_pixels} px)', fontsize=12)
    axes[1, 0].axis('off')
    
    axes[1, 1].imshow(missed, cmap='hot')
    axes[1, 1].set_title(f'Missed Items ({missed_pixels} px)', fontsize=12, color='red')
    axes[1, 1].axis('off')
    
    axes[1, 2].imshow(over_removed, cmap='hot')
    axes[1, 2].set_title(f'Over-Removed ({over_removed_pixels} px)', fontsize=12, color='orange')
    axes[1, 2].axis('off')
    
    plt.tight_layout()
    
    output_path = 'difference_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nVisualization saved to: {output_path}")
    plt.close()
    
    # Analyze characteristics of missed items
    if missed_pixels > 0:
        print("\n=== Analyzing Missed Items ===")
        # Find contours of missed items
        contours, _ = cv2.findContours(missed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        areas = []
        widths = []
        heights = []
        aspect_ratios = []
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if area > 10:  # Filter noise
                areas.append(area)
                widths.append(w)
                heights.append(h)
                aspect_ratios.append(w/h if h > 0 else 0)
        
        if areas:
            print(f"Number of missed regions: {len(areas)}")
            print(f"Area range: {min(areas):.0f} - {max(areas):.0f} pixels (avg: {np.mean(areas):.0f})")
            print(f"Width range: {min(widths)} - {max(widths)} pixels (avg: {np.mean(widths):.1f})")
            print(f"Height range: {min(heights)} - {max(heights)} pixels (avg: {np.mean(heights):.1f})")
            print(f"Aspect ratio range: {min(aspect_ratios):.2f} - {max(aspect_ratios):.2f} (avg: {np.mean(aspect_ratios):.2f})")
    
    # Analyze characteristics of over-removed items
    if over_removed_pixels > 0:
        print("\n=== Analyzing Over-Removed Items ===")
        contours, _ = cv2.findContours(over_removed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        areas = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 10:
                areas.append(area)
        
        if areas:
            print(f"Number of over-removed regions: {len(areas)}")
            print(f"Area range: {min(areas):.0f} - {max(areas):.0f} pixels (avg: {np.mean(areas):.0f})")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        auto_path = sys.argv[1]
    else:
        auto_path = 'IMG_9236_improved.JPEG'
    
    analyze_differences(
        'IMG_9236.JPEG',
        'IMG_9236_cleaned_up_manually.jpg',
        auto_path
    )

