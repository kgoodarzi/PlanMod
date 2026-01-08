"""
Programmatically remove text and leaders (arrows/pointers) from technical diagrams.

This script uses OpenCV to detect and remove text labels and leader lines
from blueprint-style technical drawings while preserving structural elements.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse


def detect_text_regions(image, method='morphology'):
    """
    Detect text regions in the image.
    
    Args:
        image: Input grayscale image
        method: 'morphology' or 'ocr' (morphology is faster, OCR is more accurate)
    
    Returns:
        Binary mask of text regions
    """
    if method == 'morphology':
        # Method 1: Morphological operations to detect text-like patterns
        # Text in technical drawings is usually small, dense, and rectangular
        
        # Use adaptive thresholding for better text detection
        # This handles varying lighting/contrast better
        binary = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        # Also try simple threshold for comparison
        _, binary_simple = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
        
        # Combine both thresholding methods
        binary = cv2.bitwise_or(binary, binary_simple)
        
        # Create kernels for different text orientations
        # Use multiple kernel sizes to catch different text sizes
        img_diagonal = np.sqrt(image.shape[0]**2 + image.shape[1]**2)
        kernel_size_h = max(20, int(img_diagonal * 0.03))  # ~3% of diagonal
        kernel_size_v = max(20, int(img_diagonal * 0.03))
        
        # Horizontal text (wider than tall)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size_h, 1))
        detected_horizontal = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, horizontal_kernel)
        
        # Vertical text (taller than wide)
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_size_v))
        detected_vertical = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, vertical_kernel)
        
        # Smaller kernels for smaller text
        small_h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, kernel_size_h//2), 1))
        small_v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, kernel_size_v//2)))
        detected_small_h = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, small_h_kernel)
        detected_small_v = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, small_v_kernel)
        
        # Combine all detections
        text_mask = cv2.bitwise_or(detected_horizontal, detected_vertical)
        text_mask = cv2.bitwise_or(text_mask, detected_small_h)
        text_mask = cv2.bitwise_or(text_mask, detected_small_v)
        
        # Also look for isolated text characters (single letters/numbers)
        # Use opening to find small connected components
        kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        isolated = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small)
        isolated = cv2.morphologyEx(isolated, cv2.MORPH_CLOSE, kernel_small)
        
        # Find all connected components in the binary image
        # This helps catch text that might not be caught by morphological operations
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        # Find contours of text regions
        contours, _ = cv2.findContours(text_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        isolated_contours, _ = cv2.findContours(isolated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Combine both sets of contours
        all_contours = list(contours) + list(isolated_contours)
        
        # Add connected components that look like text
        img_area = image.shape[0] * image.shape[1]
        for i in range(1, num_labels):  # Skip background (label 0)
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            area = stats[i, cv2.CC_STAT_AREA]
            aspect_ratio = w / h if h > 0 else 0
            
            # Check if this component looks like text
            max_area = min(3000, img_area * 0.015)
            if (10 < area < max_area and 
                0.1 < aspect_ratio < 12 and 
                w > 3 and h > 3 and
                w < 350 and h < 350):  # Reasonable size limits
                # Create contour from bounding box
                rect = np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]], dtype=np.int32)
                all_contours.append(rect.reshape(-1, 1, 2))
        
        # Filter contours by size and aspect ratio (text is typically small and rectangular)
        text_regions = np.zeros_like(image)
        img_area = image.shape[0] * image.shape[1]
        
        for contour in all_contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # Text characteristics based on analysis:
            # - Missed text can be larger: area up to ~2700, width up to ~300, height up to ~290
            # - Small to medium size (not too large relative to image)
            # - Reasonable aspect ratio (not extremely wide or tall)
            # - Minimum area to filter noise, but lower threshold for small text
            max_area = min(3000, img_area * 0.015)  # Max 1.5% of image or 3000 pixels (increased)
            min_area = 10  # Lower minimum to catch small text
            
            # More lenient aspect ratio for text (can be square-ish or slightly rectangular)
            # Text can be wider or taller depending on orientation
            if (min_area < area < max_area and 
                0.1 < aspect_ratio < 12 and  # More lenient for wider text
                w > 3 and h > 3):
                # Fill the bounding rectangle with padding
                padding = 3
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(image.shape[1], x + w + padding)
                y2 = min(image.shape[0], y + h + padding)
                cv2.rectangle(text_regions, (x1, y1), (x2, y2), 255, -1)
        
        return text_regions
    
    elif method == 'ocr':
        # Method 2: Use OCR to detect text regions (requires pytesseract)
        try:
            import pytesseract
            from PIL import Image
            
            # Get text bounding boxes
            data = pytesseract.image_to_data(Image.fromarray(image), output_type=pytesseract.Output.DICT)
            
            text_regions = np.zeros_like(image)
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if int(data['conf'][i]) > 0:  # Confidence > 0
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    cv2.rectangle(text_regions, (x, y), (x + w, y + h), 255, -1)
            
            return text_regions
        except ImportError:
            print("pytesseract not available, falling back to morphology method")
            return detect_text_regions(image, method='morphology')


def detect_leaders(image):
    """
    Detect leader lines (arrows/pointers) in the image.
    
    Leaders are typically:
    - Very short line segments (much shorter than structural elements)
    - Often connected to text
    - May have arrowheads
    
    Returns:
        Binary mask of leader regions
    """
    # Threshold to get binary image
    _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
    
    # Detect edges for line detection
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    
    # Detect lines using HoughLinesP
    # Adjust parameters based on image size
    img_diagonal = np.sqrt(image.shape[0]**2 + image.shape[1]**2)
    
    # Leaders are MUCH shorter than structural elements
    # Use a more conservative max length (only very short lines)
    max_leader_length = int(img_diagonal * 0.08)  # Max 8% of diagonal (was 15%)
    min_leader_length = 3
    
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=25, 
                            minLineLength=min_leader_length, maxLineGap=2)
    
    leader_mask = np.zeros_like(image)
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            # Only accept very short lines as leaders
            # This avoids removing structural elements
            if min_leader_length < length < max_leader_length:
                # Check if line is isolated (not part of a larger structure)
                # Draw line with minimal thickness
                thickness = 2
                cv2.line(leader_mask, (x1, y1), (x2, y2), 255, thickness)
    
    # Detect small isolated features that might be arrowheads or line endpoints
    # Use morphological operations to find small blobs
    kernel_small = np.ones((3, 3), np.uint8)
    kernel_medium = np.ones((5, 5), np.uint8)
    
    # Find small bright features
    small_features = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small)
    small_features = cv2.morphologyEx(small_features, cv2.MORPH_CLOSE, kernel_medium)
    
    # Find contours (potential arrowheads or line endpoints)
    contours, _ = cv2.findContours(small_features, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = image.shape[0] * image.shape[1]
    
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Only very small isolated features are likely arrowheads
        # Be more conservative to avoid removing structural elements
        max_feature_area = min(150, img_area * 0.0005)  # Max 0.05% of image or 150 pixels (was 300)
        if 3 < area < max_feature_area and w < 30 and h < 30:  # Smaller max size
            # Check if feature is isolated (not near large structures)
            # This helps avoid removing parts of structural elements
            cv2.drawContours(leader_mask, [contour], -1, 255, -1)
    
    return leader_mask


def filter_structural_elements(mask, original_gray):
    """
    Remove structural elements from the mask to preserve them.
    
    Structural elements are:
    - Long continuous lines
    - Large features
    - Thick lines
    - Connected components that span significant portions of the image
    
    Args:
        mask: Binary mask of regions to remove
        original_gray: Original grayscale image
    
    Returns:
        Filtered mask with structural elements removed
    """
    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    filtered_mask = np.zeros_like(mask)
    img_area = original_gray.shape[0] * original_gray.shape[1]
    img_diagonal = np.sqrt(original_gray.shape[0]**2 + original_gray.shape[1]**2)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        length = max(w, h)
        width = min(w, h)
        aspect_ratio = w / h if h > 0 else 0
        
        # Structural elements are:
        # - Very long lines (longer than typical leaders/text)
        # - Large areas (much bigger than typical text)
        # - Thick lines (width > threshold)
        # - Features that span significant portions of image dimensions
        is_structural = False
        
        # Check if it's a very long line (structural element like frame lines)
        if length > img_diagonal * 0.12:  # Longer than 12% of diagonal
            is_structural = True
        
        # Check if it's a very large feature (structural element)
        if area > img_area * 0.015:  # Larger than 1.5% of image (increased threshold)
            is_structural = True
        
        # Check if it spans a significant portion of image width or height
        if w > original_gray.shape[1] * 0.3 or h > original_gray.shape[0] * 0.3:
            is_structural = True
        
        # Check if it's a thick line (structural element, not a leader)
        # Leaders are thin, structural elements are thicker
        if width > 8 and length > img_diagonal * 0.08:  # Thick and reasonably long
            is_structural = True
        
        # Check if it has very high aspect ratio (very long thin line - could be structural)
        # But only if it's also reasonably long
        if aspect_ratio > 20 and length > img_diagonal * 0.1:
            is_structural = True
        if aspect_ratio < 0.05 and length > img_diagonal * 0.1:  # Very tall thin line
            is_structural = True
        
        # Only keep non-structural elements in the mask
        if not is_structural:
            cv2.drawContours(filtered_mask, [contour], -1, 255, -1)
    
    return filtered_mask


def remove_text_and_leaders(image_path, output_path=None, method='morphology', 
                            use_inpainting=True, dilation_size=3):
    """
    Remove text and leaders from a technical diagram.
    
    Args:
        image_path: Path to input image
        output_path: Path to save output image (default: adds '_cleaned' suffix)
        method: Text detection method ('morphology' or 'ocr')
        use_inpainting: If True, use inpainting to fill removed regions
        dilation_size: Size of dilation kernel for expanding removal regions
    
    Returns:
        Cleaned image
    """
    # Read image
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Invert if needed (assume black text on white background)
    # For technical drawings, usually already black on white
    if np.mean(gray) > 127:  # Mostly white background
        # Text is dark, so we work with inverted image for detection
        work_image = 255 - gray
    else:
        work_image = gray.copy()
    
    # Detect text regions
    print("Detecting text regions...")
    text_mask = detect_text_regions(work_image, method=method)
    
    # Detect leaders
    print("Detecting leader lines...")
    leader_mask = detect_leaders(work_image)
    
    # Combine masks
    combined_mask = cv2.bitwise_or(text_mask, leader_mask)
    
    # Filter out structural elements to preserve them
    print("Filtering structural elements...")
    combined_mask = filter_structural_elements(combined_mask, gray)
    
    # Dilate mask to ensure complete removal (but less aggressively)
    kernel = np.ones((dilation_size, dilation_size), np.uint8)
    combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)  # Reduced from 2 to 1
    
    # Apply mask to original image
    if use_inpainting:
        print("Inpainting removed regions...")
        # Inpainting works on non-zero (white) regions in the mask
        # Our mask has white (255) where we want to remove, which is correct
        mask_for_inpaint = combined_mask.copy()
        # Use INPAINT_TELEA for better results on technical drawings
        result = cv2.inpaint(img, mask_for_inpaint, 5, cv2.INPAINT_TELEA)
    else:
        # Simple approach: set removed regions to white
        result = img.copy()
        mask_3channel = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
        result[mask_3channel > 0] = 255
    
    # Save result
    if output_path is None:
        input_path = Path(image_path)
        output_path = input_path.parent / f"{input_path.stem}_cleaned{input_path.suffix}"
    
    cv2.imwrite(str(output_path), result)
    print(f"Saved cleaned image to: {output_path}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Remove text and leaders from technical diagrams'
    )
    parser.add_argument('input', type=str, help='Input image path')
    parser.add_argument('-o', '--output', type=str, default=None, 
                       help='Output image path (default: adds _cleaned suffix)')
    parser.add_argument('-m', '--method', type=str, default='morphology',
                       choices=['morphology', 'ocr'],
                       help='Text detection method (default: morphology)')
    parser.add_argument('--no-inpaint', action='store_true',
                       help='Disable inpainting (use white fill instead)')
    parser.add_argument('-d', '--dilation', type=int, default=3,
                       help='Dilation size for mask expansion (default: 3)')
    
    args = parser.parse_args()
    
    result = remove_text_and_leaders(
        args.input,
        args.output,
        method=args.method,
        use_inpainting=not args.no_inpaint,
        dilation_size=args.dilation
    )
    
    print("Done!")


if __name__ == '__main__':
    main()

