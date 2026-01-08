"""
Visualize text detection results from OCR.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

try:
    import pytesseract
    from PIL import Image
    import os
    import platform
    
    # Auto-detect Tesseract path on Windows
    if platform.system() == 'Windows':
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME')),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
except ImportError:
    print("pytesseract not available")
    sys.exit(1)


def visualize_detection(image_path, output_path=None):
    """Visualize OCR text detection on image."""
    
    # Read image
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Could not read: {image_path}")
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    pil_image = Image.fromarray(gray)
    
    # Get OCR data
    ocr_data = pytesseract.image_to_data(
        pil_image,
        output_type=pytesseract.Output.DICT,
        config='--psm 11'  # Sparse text mode
    )
    
    # Create visualization
    vis_img = img.copy()
    text_mask = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
    
    n_boxes = len(ocr_data['text'])
    text_count = 0
    
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = int(ocr_data['conf'][i])
        
        if conf > 30 and text:
            x = ocr_data['left'][i]
            y = ocr_data['top'][i]
            w = ocr_data['width'][i]
            h = ocr_data['height'][i]
            
            # Draw rectangle
            cv2.rectangle(vis_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Draw text label
            cv2.putText(vis_img, f"{text} ({conf}%)", (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Add to mask
            cv2.rectangle(text_mask, (x, y), (x + w, y + h), 255, -1)
            text_count += 1
    
    print(f"Detected {text_count} text regions")
    
    # Create comparison figure
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0].set_title('Original Image', fontsize=12, fontweight='bold')
    axes[0].axis('off')
    
    axes[1].imshow(cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB))
    axes[1].set_title(f'Text Detection ({text_count} regions)', fontsize=12, fontweight='bold')
    axes[1].axis('off')
    
    axes[2].imshow(text_mask, cmap='hot')
    axes[2].set_title('Detection Mask', fontsize=12, fontweight='bold')
    axes[2].axis('off')
    
    plt.tight_layout()
    
    if output_path is None:
        output_path = Path(image_path).stem + '_detection_vis.png'
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Visualization saved to: {output_path}")
    plt.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = 'IMG_9236.JPEG'
    
    visualize_detection(image_path)

