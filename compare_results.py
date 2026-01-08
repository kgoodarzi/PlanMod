"""
Compare original and cleaned images side by side.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys


def compare_images(original_path, cleaned_path, output_path=None):
    """Create a side-by-side comparison of original and cleaned images."""
    
    # Read images
    original = cv2.imread(str(original_path))
    cleaned = cv2.imread(str(cleaned_path))
    
    if original is None:
        print(f"Could not read: {original_path}")
        return
    if cleaned is None:
        print(f"Could not read: {cleaned_path}")
        return
    
    # Convert BGR to RGB for matplotlib
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    cleaned_rgb = cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB)
    
    # Create comparison figure
    fig, axes = plt.subplots(1, 2, figsize=(16, 10))
    
    axes[0].imshow(original_rgb)
    axes[0].set_title('Original Image', fontsize=14, fontweight='bold')
    axes[0].axis('off')
    
    axes[1].imshow(cleaned_rgb)
    axes[1].set_title('Cleaned Image (Text & Leaders Removed)', fontsize=14, fontweight='bold')
    axes[1].axis('off')
    
    plt.tight_layout()
    
    if output_path is None:
        output_path = Path(original_path).stem + '_comparison.png'
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Comparison saved to: {output_path}")
    plt.close()


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        original = sys.argv[1]
        cleaned = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else None
    else:
        # Default to sample files
        original = 'IMG_9236.JPEG'
        cleaned = 'IMG_9236_cleaned_v2.JPEG'
        output = None
    
    compare_images(original, cleaned, output)

