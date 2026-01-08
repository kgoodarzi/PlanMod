"""
Diagnostic script to visualize text and leader detection on sample images.
This helps tune the detection parameters.
"""

import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt


def visualize_detection(image_path):
    """Visualize what the script detects as text and leaders."""
    
    # Read image
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Could not read image: {image_path}")
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Check if we need to invert
    if np.mean(gray) > 127:
        work_image = 255 - gray
        print("Image inverted for processing (white background detected)")
    else:
        work_image = gray.copy()
    
    # Import detection functions
    from remove_text_leaders import detect_text_regions, detect_leaders
    
    # Detect text
    print("Detecting text regions...")
    text_mask = detect_text_regions(work_image, method='morphology')
    
    # Detect leaders
    print("Detecting leader lines...")
    leader_mask = detect_leaders(work_image)
    
    # Combine masks
    combined_mask = cv2.bitwise_or(text_mask, leader_mask)
    
    # Create visualization
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # Original
    axes[0, 0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0, 0].set_title('Original Image')
    axes[0, 0].axis('off')
    
    # Grayscale
    axes[0, 1].imshow(gray, cmap='gray')
    axes[0, 1].set_title('Grayscale')
    axes[0, 1].axis('off')
    
    # Work image
    axes[0, 2].imshow(work_image, cmap='gray')
    axes[0, 2].set_title('Work Image (for detection)')
    axes[0, 2].axis('off')
    
    # Text mask
    axes[1, 0].imshow(text_mask, cmap='hot')
    axes[1, 0].set_title(f'Text Detection ({np.sum(text_mask > 0)} pixels)')
    axes[1, 0].axis('off')
    
    # Leader mask
    axes[1, 1].imshow(leader_mask, cmap='hot')
    axes[1, 1].set_title(f'Leader Detection ({np.sum(leader_mask > 0)} pixels)')
    axes[1, 1].axis('off')
    
    # Combined mask overlaid on original
    overlay = img.copy()
    combined_mask_rgb = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
    overlay[combined_mask > 0] = [0, 255, 0]  # Green overlay
    result = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)
    axes[1, 2].imshow(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
    axes[1, 2].set_title('Detection Overlay (Green = to be removed)')
    axes[1, 2].axis('off')
    
    plt.tight_layout()
    
    output_path = Path(image_path).stem + '_detection_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nVisualization saved to: {output_path}")
    print(f"Text pixels detected: {np.sum(text_mask > 0)}")
    print(f"Leader pixels detected: {np.sum(leader_mask > 0)}")
    print(f"Total pixels to remove: {np.sum(combined_mask > 0)}")
    
    plt.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Default to sample image
        image_path = 'IMG_9236.JPEG'
    
    visualize_detection(image_path)

