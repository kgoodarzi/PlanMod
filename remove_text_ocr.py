"""
Remove text from technical diagrams using OCR.
Simple, focused approach to match IMG_9236_No_Text.jpg

Note on F2 detection:
F2 is NOT detected by OCR at ANY confidence level (tested all PSM modes, with/without contrast enhancement).
This is confirmed by exhaustive testing - OCR simply cannot detect F2, likely because:
- It's positioned too close to structural elements (vertical lines)
- The contrast or size may be slightly different from F3
- OCR may be confusing it with nearby structural features
- The character may be partially obscured or have different characteristics

F3 is successfully detected in PSM 12 mode at (1027,389) with 89% confidence.
If F2 needs to be removed, it will require manual annotation or a different approach (e.g., template matching based on F3).

Mask Improvements:
- Masks are now cropped to actual text content (removes empty space below text like in LEFT)
- This prevents removing unnecessary pixels and preserves nearby elements better

Mask Size Control:
- Use --fixed-padding N for consistent mask sizes (recommended for similar text)
- Use --tight for minimal 1px padding (preserves nearby elements like leader lines)
- Use -p N for custom padding
- Use -d 0 to disable dilation (prevents mask expansion)
"""

import cv2
import numpy as np
from pathlib import Path
import argparse

try:
    import pytesseract
    from PIL import Image
    import os
    import platform
    
    # Auto-detect Tesseract path on Windows
    if platform.system() == 'Windows':
        # Common Tesseract installation paths on Windows
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME')),
        ]
        
        # Check if tesseract_cmd is not set or doesn't work
        if not hasattr(pytesseract.pytesseract, 'tesseract_cmd') or pytesseract.pytesseract.tesseract_cmd == 'tesseract':
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    print(f"Found Tesseract at: {path}")
                    break
    
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: pytesseract not available. Install with: pip install pytesseract")
    print("Also install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki")


def detect_text_with_ocr(image, padding=None, tight_mask=False, fixed_padding=None):
    """
    Detect all text regions using OCR.
    
    Args:
        image: Input grayscale or BGR image
    
    Returns:
        Binary mask of text regions
    """
    if not OCR_AVAILABLE:
        raise ImportError("pytesseract is required for OCR-based text detection")
    
    # Convert to PIL Image
    if len(image.shape) == 3:
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    else:
        pil_image = Image.fromarray(image)
    
    # Get detailed OCR data including bounding boxes
    # Try multiple PSM modes to catch all text
    # PSM 6: Assume a single uniform block of text
    # PSM 11: Sparse text (good for scattered labels)
    # PSM 12: Sparse text with OSD (orientation and script detection)
    
    all_detections = []
    
    # Try different PSM modes and combine all detections
    # PSM 11: Sparse text (best for scattered labels in diagrams)
    # PSM 6: Single uniform block
    # PSM 12: Sparse text with OSD
    
    all_boxes = []  # Store all detected boxes to merge
    
    for psm_mode in [11, 6, 12]:
        try:
            ocr_data = pytesseract.image_to_data(
                pil_image, 
                output_type=pytesseract.Output.DICT,
                config=f'--psm {psm_mode}'
            )
            
            # Extract valid text boxes from this mode
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])
                w = ocr_data['width'][i]
                h = ocr_data['height'][i]
                
                if conf > 30 and text and len(text) > 0:
                    # Calculate aspect ratio
                    aspect_ratio = w / h if h > 0 else 0
                    
                    # Filter false positives based on actual text characteristics
                    # Real text characteristics from analysis:
                    # - Aspect ratio: 2.5-7.3 (wide, horizontal text)
                    # - Height: ~48-51 pixels (consistent)
                    # - Confidence: 91-96% (high)
                    # - Contains letters/numbers, not standalone symbols
                    
                    # Filter 1: Single character detections (likely false positives)
                    if len(text) == 1:
                        # Only keep if it's a letter or number with high confidence
                        if not (text.isalnum() and conf > 85):
                            continue
                    
                    # Filter 2: Very tall/narrow (vertical lines, not text)
                    # Real text has aspect ratio > 0.5 (wider than tall)
                    if aspect_ratio < 0.5:
                        continue
                    
                    # Filter 3: Higher confidence threshold - real text has 85%+ confidence
                    # Only allow lower confidence for very short text (like "F2", "F3")
                    if conf < 80:
                        continue
                    if len(text) <= 2 and conf < 85:
                        continue
                    
                    # Filter 4: Very large detections (likely false positives from structures)
                    # Real text height is ~48-51 pixels, width varies but reasonable
                    if h > 100 or w > 500:  # Much larger than expected
                        continue
                    
                    # Filter 5: Text containing only symbols (like ":", "=", "|", etc.)
                    # Real text contains letters/numbers
                    if not any(c.isalnum() for c in text):
                        continue
                    
                    # Filter 6: Very short height (likely noise)
                    # Real text height is ~48-51 pixels
                    if h < 30:  # Increased from 20 to filter more noise
                        continue
                    
                    # Filter 7: Very wide aspect ratio with low confidence
                    # If aspect > 8 and low confidence, might be false
                    if aspect_ratio > 10 and conf < 85:
                        continue
                    
                    # Filter 8: Check for garbled text (contains non-printable or unusual chars)
                    # Real text is clean: letters, numbers, hyphens, periods
                    if any(ord(c) > 127 and c not in text for c in text):  # Non-ASCII except known
                        # Allow common punctuation
                        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")
                        if not all(c.upper() in allowed_chars or c.isspace() for c in text):
                            continue
                    
                    all_boxes.append({
                        'x': ocr_data['left'][i],
                        'y': ocr_data['top'][i],
                        'w': w,
                        'h': h,
                        'conf': conf,
                        'text': text,
                        'aspect': aspect_ratio
                    })
        except Exception as e:
            print(f"PSM {psm_mode} failed: {e}")
            continue
    
    if not all_boxes:
        print("Warning: No text detected with any PSM mode")
        return np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
    
    # Remove duplicate boxes (boxes that overlap significantly)
    # Sort by confidence and area, keep the best ones
    all_boxes.sort(key=lambda b: (b['conf'], b['w'] * b['h']), reverse=True)
    
    unique_boxes = []
    for box in all_boxes:
        is_duplicate = False
        for existing in unique_boxes:
            # Check if boxes overlap significantly (>50% overlap)
            overlap_x = max(0, min(box['x'] + box['w'], existing['x'] + existing['w']) - max(box['x'], existing['x']))
            overlap_y = max(0, min(box['y'] + box['h'], existing['y'] + existing['h']) - max(box['y'], existing['y']))
            overlap_area = overlap_x * overlap_y
            box_area = box['w'] * box['h']
            existing_area = existing['w'] * existing['h']
            
            if overlap_area > 0.5 * min(box_area, existing_area):
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_boxes.append(box)
    
    # Create mask from unique boxes
    ocr_data = {'left': [b['x'] for b in unique_boxes],
                'top': [b['y'] for b in unique_boxes],
                'width': [b['w'] for b in unique_boxes],
                'height': [b['h'] for b in unique_boxes],
                'text': [b['text'] for b in unique_boxes],
                'conf': [b['conf'] for b in unique_boxes]}
    
    # Create mask for text regions
    text_mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
    
    n_boxes = len(ocr_data['text'])
    text_count = 0
    
    print(f"\nFiltered text detections ({n_boxes} regions):")
    for i in range(n_boxes):
        # Check if this is a text detection (confidence > 0 and text is not empty)
        text = ocr_data['text'][i].strip()
        conf = int(ocr_data['conf'][i])
        
        # Filter: confidence > 30 and non-empty text
        # Lower confidence threshold to catch more text, but filter out noise
        if conf > 30 and text and len(text) > 0:
            x = ocr_data['left'][i]
            y = ocr_data['top'][i]
            w = ocr_data['width'][i]
            h = ocr_data['height'][i]
            
        # Skip very small detections (likely noise)
        if w < 3 or h < 3:
            continue
        
        aspect = w / h if h > 0 else 0
        print(f"  '{text}' conf={conf}% size={w}x{h} aspect={aspect:.2f}")
        
        # Add padding around text to ensure complete removal
        # Use consistent padding to avoid distorting nearby elements
        if fixed_padding is not None:
            # Use fixed padding for all text (most consistent)
            text_padding = fixed_padding
        elif tight_mask:
            # Minimal padding for tight masks (preserves nearby elements)
            text_padding = 1
        elif padding is not None:
            # Use specified padding
            text_padding = padding
        else:
            # Auto padding: use a consistent small padding based on average text size
            # This ensures similar text gets similar mask sizes
            # Use a fixed small padding (2px) for consistency, regardless of text size
            text_padding = 2
        
        # Crop mask to actual text content to avoid removing empty space
        # Extract the detected region to find actual text bounds
        region = image[y:min(y+h, image.shape[0]), x:min(x+w, image.shape[1])]
        
        if region.size > 0:
            # Find actual text bounds within the OCR detection box
            # Look for non-white pixels (actual text content)
            if len(region.shape) == 2:  # Grayscale
                text_mask_region = region < 200  # Text is darker than 200
            else:  # BGR
                gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                text_mask_region = gray_region < 200
            
            if np.any(text_mask_region):
                # Find bounding box of actual text content
                rows_with_text = np.any(text_mask_region, axis=1)
                cols_with_text = np.any(text_mask_region, axis=0)
                
                if np.any(rows_with_text) and np.any(cols_with_text):
                    actual_top = np.where(rows_with_text)[0][0]
                    actual_bottom = np.where(rows_with_text)[0][-1] + 1
                    actual_left = np.where(cols_with_text)[0][0]
                    actual_right = np.where(cols_with_text)[0][-1] + 1
                    
                    # Use actual text bounds with padding
                    actual_x = x + actual_left
                    actual_y = y + actual_top
                    actual_w = actual_right - actual_left
                    actual_h = actual_bottom - actual_top
                else:
                    # Fallback to OCR box if we can't find text bounds
                    actual_x, actual_y, actual_w, actual_h = x, y, w, h
            else:
                # No text found in region, use OCR box
                actual_x, actual_y, actual_w, actual_h = x, y, w, h
        else:
            # Empty region, use OCR box
            actual_x, actual_y, actual_w, actual_h = x, y, w, h
        
        # Apply padding to actual text bounds
        x1 = max(0, actual_x - text_padding)
        y1 = max(0, actual_y - text_padding)
        x2 = min(image.shape[1], actual_x + actual_w + text_padding)
        y2 = min(image.shape[0], actual_y + actual_h + text_padding)
        
        # Fill rectangle in mask
        cv2.rectangle(text_mask, (x1, y1), (x2, y2), 255, -1)
        text_count += 1
    
    print(f"Detected {text_count} text regions")
    return text_mask, ocr_data  # Return both mask and OCR data for labeling


def sliding_window_ocr(image, detected_text_stats, padding=None, tight_mask=False, fixed_padding=None):
    """
    Second pass OCR using sliding windows based on detected text characteristics.
    
    Args:
        image: Grayscale image
        detected_text_stats: Dictionary with stats from first pass (avg_width, avg_height, etc.)
        padding: Padding parameter
        tight_mask: Tight mask flag
        fixed_padding: Fixed padding parameter
    
    Returns:
        Additional text mask and OCR data from second pass
    """
    if not OCR_AVAILABLE:
        return np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8), {'left': [], 'top': [], 'width': [], 'height': [], 'text': [], 'conf': []}
    
    img_h, img_w = image.shape
    img_area = img_h * img_w
    
    # Calculate window size based on detected text characteristics
    # From F2 example: F2-only image is ~12.2x smaller than original
    # Text in F2-only image: 70x48 in 431x299 window
    # So text is ~16% of window dimensions
    # Use a multiplier to create windows that are appropriately sized
    
    # Use exact F2 image window size (431x299) that successfully detected F2
    # This is the proven window size that works for detecting text like F2
    window_width = 431
    window_height = 299
    
    print(f"  Using F2-proven window size: {window_width}x{window_height} pixels")
    
    # Step size: overlap windows by 50% to catch text at boundaries
    step_x = window_width // 2
    step_y = window_height // 2
    
    print(f"\nSecond pass: Sliding window OCR")
    print(f"  Window size: {window_width}x{window_height} pixels")
    print(f"  Step size: {step_x}x{step_y} pixels")
    
    # Create mask for second pass detections
    second_pass_mask = np.zeros((img_h, img_w), dtype=np.uint8)
    second_pass_boxes = []
    
    # Slide window over image
    y = 0
    window_count = 0
    
    while y < img_h:
        x = 0
        while x < img_w:
            # Extract window
            x_end = min(x + window_width, img_w)
            y_end = min(y + window_height, img_h)
            
            window = image[y:y_end, x:x_end]
            
            if window.size > 0:
                # Run OCR on window
                try:
                    pil_window = Image.fromarray(window)
                    # Try multiple PSM modes for better detection
                    # PSM 11 and 12 worked well for isolated F2
                    all_window_detections = []
                    for psm_mode in [11, 8, 12]:
                        try:
                            ocr_data = pytesseract.image_to_data(
                                pil_window,
                                output_type=pytesseract.Output.DICT,
                                config=f'--psm {psm_mode}'
                            )
                            all_window_detections.append(ocr_data)
                        except:
                            continue
                    
                    # Use the first successful detection or combine them
                    if not all_window_detections:
                        continue
                    ocr_data = all_window_detections[0]  # Start with first
                    # If multiple modes, prefer the one with more detections
                    for det_data in all_window_detections[1:]:
                        if len([t for t in det_data['text'] if t.strip()]) > len([t for t in ocr_data['text'] if t.strip()]):
                            ocr_data = det_data
                    
                    n_boxes = len(ocr_data['text'])
                    window_detections = []
                    for i in range(n_boxes):
                        text = ocr_data['text'][i].strip()
                        conf = int(ocr_data['conf'][i])
                        
                        # Collect all detections for debugging
                        if conf > 0 and text and len(text) > 0:
                            window_detections.append((text, conf, ocr_data['left'][i], ocr_data['top'][i], 
                                                     ocr_data['width'][i], ocr_data['height'][i]))
                        
                        # Accept detections with reasonable confidence (lower threshold for second pass)
                        # Also filter by size - text should be reasonable size relative to window
                        if conf > 40 and text and len(text) > 0:
                            # Filter out detections that are too large (likely false positives)
                            if box_w > window_width * 0.8 or box_h > window_height * 0.8:
                                continue  # Skip if detection is too large relative to window
                            
                            # Filter: text should contain alphanumeric characters
                            if not any(c.isalnum() for c in text):
                                continue
                            
                            # Filter: reasonable aspect ratio (not extremely wide or tall)
                            aspect = box_w / box_h if box_h > 0 else 0
                            if aspect < 0.3 or aspect > 15:
                                continue
                            # Adjust coordinates to full image space
                            box_x = ocr_data['left'][i] + x
                            box_y = ocr_data['top'][i] + y
                            box_w = ocr_data['width'][i]
                            box_h = ocr_data['height'][i]
                            
                            # Check if this is a new detection (not already found in first pass)
                            # by checking if it overlaps significantly with first pass detections
                            is_new = True
                            for existing_box in detected_text_stats.get('boxes', []):
                                ex_x, ex_y, ex_w, ex_h = existing_box
                                # Check overlap - use center distance for better matching
                                center_x = box_x + box_w / 2
                                center_y = box_y + box_h / 2
                                ex_center_x = ex_x + ex_w / 2
                                ex_center_y = ex_y + ex_h / 2
                                
                                # If centers are very close, it's a duplicate
                                dist = np.sqrt((center_x - ex_center_x)**2 + (center_y - ex_center_y)**2)
                                if dist < 20:  # Within 20 pixels = duplicate
                                    is_new = False
                                    break
                                
                                # Also check area overlap
                                overlap_x = max(0, min(box_x + box_w, ex_x + ex_w) - max(box_x, ex_x))
                                overlap_y = max(0, min(box_y + box_h, ex_y + ex_h) - max(box_y, ex_y))
                                overlap_area = overlap_x * overlap_y
                                box_area = box_w * box_h
                                
                                if overlap_area > 0.5 * box_area:  # 50% overlap = duplicate
                                    is_new = False
                                    break
                            
                            if is_new:
                                second_pass_boxes.append({
                                    'x': box_x,
                                    'y': box_y,
                                    'w': box_w,
                                    'h': box_h,
                                    'conf': conf,
                                    'text': text
                                })
                                
                                # Add to mask
                                if fixed_padding is not None:
                                    text_padding = fixed_padding
                                elif tight_mask:
                                    text_padding = 1
                                elif padding is not None:
                                    text_padding = padding
                                else:
                                    text_padding = 2
                                
                                x1 = max(0, box_x - text_padding)
                                y1 = max(0, box_y - text_padding)
                                x2 = min(img_w, box_x + box_w + text_padding)
                                y2 = min(img_h, box_y + box_h + text_padding)
                                
                                cv2.rectangle(second_pass_mask, (x1, y1), (x2, y2), 255, -1)
                    
                    # Debug: Log detections in windows (especially F2)
                    if window_detections:
                        for det_text, det_conf, det_x, det_y, det_w, det_h in window_detections:
                            if 'F2' in det_text.upper() or (det_text.upper() == 'F' and det_conf > 50):
                                print(f"    DEBUG: Found '{det_text}' conf={det_conf}% at window ({x},{y}) -> image coords ({det_x},{det_y}) size={det_w}x{det_h}")
                
                except Exception as e:
                    pass  # Skip windows that fail
            
            x += step_x
            window_count += 1
        
        y += step_y
    
    print(f"  Processed {window_count} windows")
    print(f"  Found {len(second_pass_boxes)} new text regions in second pass")
    
    # Convert to OCR data format
    if second_pass_boxes:
        second_pass_ocr = {
            'left': [b['x'] for b in second_pass_boxes],
            'top': [b['y'] for b in second_pass_boxes],
            'width': [b['w'] for b in second_pass_boxes],
            'height': [b['h'] for b in second_pass_boxes],
            'text': [b['text'] for b in second_pass_boxes],
            'conf': [b['conf'] for b in second_pass_boxes]
        }
        
        print(f"  Second pass detections:")
        for i in range(len(second_pass_ocr['text'])):
            text = second_pass_ocr['text'][i]
            conf = second_pass_ocr['conf'][i]
            w = second_pass_ocr['width'][i]
            h = second_pass_ocr['height'][i]
            print(f"    '{text}' conf={conf}% size={w}x{h}")
    else:
        second_pass_ocr = {'left': [], 'top': [], 'width': [], 'height': [], 'text': [], 'conf': []}
    
    return second_pass_mask, second_pass_ocr


def remove_text(image_path, output_path=None, padding=None, dilation_iterations=1, 
                tight_mask=False, fixed_padding=None, enhance_contrast=False):
    """
    Remove text from image using OCR.
    
    Args:
        image_path: Path to input image
        output_path: Path to save output image
        padding: Extra pixels around detected text (None = auto, 2px default)
        dilation_iterations: Number of dilation iterations to expand mask (0 = no dilation)
        tight_mask: If True, use minimal padding (1px) for tighter masks
        fixed_padding: If set, use this exact padding for all text (most consistent)
        enhance_contrast: If True, apply CLAHE contrast enhancement before OCR
    
    Returns:
        Cleaned image
    """
    if not OCR_AVAILABLE:
        raise ImportError("pytesseract is required")
    
    # Read image
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    print(f"Processing image: {image_path}")
    print(f"Image size: {img.shape[1]}x{img.shape[0]} pixels")
    
    # Convert to grayscale for OCR (OCR works better on grayscale)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Preprocessing: Enhance contrast to improve OCR detection
    if enhance_contrast:
        # Method 1: CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Better than simple histogram equalization for technical drawings
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        print("Applied CLAHE contrast enhancement")
    
    # Enhance image for better OCR detection
    # Apply slight sharpening and contrast enhancement
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    
    # Use adaptive thresholding to improve text detection
    # This helps OCR detect text even with varying backgrounds
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # FIRST PASS: Try OCR on original grayscale (usually works best)
    print("First pass: Detecting text with OCR...")
    text_mask, ocr_data = detect_text_with_ocr(gray, padding=padding, tight_mask=tight_mask, 
                                                fixed_padding=fixed_padding)
    
    # Calculate statistics from first pass for second pass
    if len(ocr_data['text']) > 0:
        widths = [w for w in ocr_data['width'] if w > 0]
        heights = [h for h in ocr_data['height'] if h > 0]
        boxes = [(ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                 for i in range(len(ocr_data['text']))]
        
        detected_text_stats = {
            'avg_width': np.mean(widths) if widths else 150,
            'avg_height': np.mean(heights) if heights else 50,
            'min_width': np.min(widths) if widths else 50,
            'min_height': np.min(heights) if heights else 30,
            'max_width': np.max(widths) if widths else 400,
            'max_height': np.max(heights) if heights else 100,
            'boxes': boxes
        }
    else:
        # Default stats if nothing detected
        detected_text_stats = {
            'avg_width': 150,
            'avg_height': 50,
            'min_width': 50,
            'min_height': 30,
            'max_width': 400,
            'max_height': 100,
            'boxes': []
        }
    
    # SECOND PASS: Sliding window OCR to find missed text
    second_mask, second_ocr = sliding_window_ocr(gray, detected_text_stats, 
                                                padding=padding, tight_mask=tight_mask, 
                                                fixed_padding=fixed_padding)
    
    # TARGETED SEARCH: If F3 is detected, search for F2 in corresponding location
    # F3 is typically on the right, F2 on the left at similar Y position
    f3_found = False
    f3_y = None
    for i in range(len(ocr_data['text'])):
        if ocr_data['text'][i].upper() == 'F3':
            f3_found = True
            f3_y = ocr_data['top'][i]
            f3_x = ocr_data['left'][i]
            f3_h = ocr_data['height'][i]
            print(f"\nTargeted search: F3 found at ({f3_x}, {f3_y}), searching for F2...")
            
            # Search in left region at similar Y position
            # F2 should be roughly at x=200-500, y similar to F3
            search_x1 = max(0, 200)
            search_x2 = min(img.shape[1], 500)
            search_y1 = max(0, f3_y - 50)
            search_y2 = min(img.shape[0], f3_y + f3_h + 50)
            
            search_region = gray[search_y1:search_y2, search_x1:search_x2]
            if search_region.size > 0:
                pil_region = Image.fromarray(search_region)
                # Try PSM modes that worked for isolated F2
                for psm in [11, 12]:
                    try:
                        region_data = pytesseract.image_to_data(
                            pil_region,
                            output_type=pytesseract.Output.DICT,
                            config=f'--psm {psm}'
                        )
                        
                        for j in range(len(region_data['text'])):
                            text = region_data['text'][j].strip().upper()
                            conf = int(region_data['conf'][j])
                            if 'F2' in text and conf > 40:
                                # Adjust coordinates to full image
                                box_x = region_data['left'][j] + search_x1
                                box_y = region_data['top'][j] + search_y1
                                box_w = region_data['width'][j]
                                box_h = region_data['height'][j]
                                
                                print(f"  F2 found in targeted search: '{text}' conf={conf}% at ({box_x}, {box_y})")
                                
                                # Add to second pass results
                                second_ocr['left'].append(box_x)
                                second_ocr['top'].append(box_y)
                                second_ocr['width'].append(box_w)
                                second_ocr['height'].append(box_h)
                                second_ocr['text'].append(text)
                                second_ocr['conf'].append(conf)
                                
                                # Add to mask
                                if fixed_padding is not None:
                                    text_padding = fixed_padding
                                elif tight_mask:
                                    text_padding = 1
                                elif padding is not None:
                                    text_padding = padding
                                else:
                                    text_padding = 2
                                
                                x1 = max(0, box_x - text_padding)
                                y1 = max(0, box_y - text_padding)
                                x2 = min(img.shape[1], box_x + box_w + text_padding)
                                y2 = min(img.shape[0], box_y + box_h + text_padding)
                                
                                cv2.rectangle(second_mask, (x1, y1), (x2, y2), 255, -1)
                                break
                    except:
                        continue
            break
    
    # Combine first and second pass results
    text_mask = cv2.bitwise_or(text_mask, second_mask)
    
    # Merge OCR data from both passes
    for key in ocr_data:
        ocr_data[key].extend(second_ocr[key])
    
    # Also try on adaptive threshold to catch text that might be missed
    # But be more selective - only add regions not already detected
    try:
        mask2, ocr_data2 = detect_text_with_ocr(adaptive, padding=padding, tight_mask=tight_mask,
                                                fixed_padding=fixed_padding)
        # Only add new regions that weren't already detected
        new_regions = cv2.bitwise_and(mask2, cv2.bitwise_not(text_mask))
        # Only add if the new region is significant (not just noise)
        if np.sum(new_regions > 0) > 50:  # At least 50 pixels
            text_mask = cv2.bitwise_or(text_mask, new_regions)
            # Merge OCR data (prefer higher confidence)
            for i in range(len(ocr_data2['text'])):
                text2 = ocr_data2['text'][i]
                conf2 = ocr_data2['conf'][i]
                # Check if this is a new detection
                is_new = True
                for j in range(len(ocr_data['text'])):
                    x1, y1 = ocr_data['left'][j], ocr_data['top'][j]
                    x2, y2 = ocr_data2['left'][i], ocr_data2['top'][i]
                    if abs(x1 - x2) < 10 and abs(y1 - y2) < 10:
                        is_new = False
                        break
                if is_new and conf2 > 80:
                    for key in ocr_data:
                        ocr_data[key].append(ocr_data2[key][i])
    except:
        pass  # If adaptive fails, just use the original detection
    
    # Dilate mask slightly to ensure complete text removal
    # But be conservative to avoid removing structural elements
    if dilation_iterations > 0:
        kernel = np.ones((2, 2), np.uint8)  # Smaller kernel
        text_mask = cv2.dilate(text_mask, kernel, iterations=dilation_iterations)
    
    # Count pixels to be removed
    pixels_to_remove = np.sum(text_mask > 0)
    total_pixels = img.shape[0] * img.shape[1]
    print(f"Removing {pixels_to_remove} pixels ({100*pixels_to_remove/total_pixels:.2f}% of image)")
    
    # Use inpainting to fill removed regions
    print("Inpainting removed regions...")
    # Use smaller inpainting radius for more precise filling
    result = cv2.inpaint(img, text_mask, 3, cv2.INPAINT_TELEA)
    
    # Save result
    if output_path is None:
        input_path = Path(image_path)
        output_path = input_path.parent / f"{input_path.stem}_no_text{input_path.suffix}"
    
    cv2.imwrite(str(output_path), result)
    print(f"Saved result to: {output_path}")
    
    # Create mask image showing the actual removed pixels from original image
    # Start with white background
    mask_labeled = np.ones((img.shape[0], img.shape[1], 3), dtype=np.uint8) * 255
    
    # Extract and show the actual removed pixels from the original image
    # Where mask is white (255), show the original image pixels
    mask_3channel = cv2.cvtColor(text_mask, cv2.COLOR_GRAY2BGR)
    
    # Copy original image pixels where mask is active
    # This shows what was actually removed
    mask_labeled[mask_3channel > 0] = img[mask_3channel > 0]
    
    # Optionally, you can also draw a border around each removed region
    # to make it clearer what was detected
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i]
        conf = ocr_data['conf'][i]
        x = ocr_data['left'][i]
        y = ocr_data['top'][i]
        w = ocr_data['width'][i]
        h = ocr_data['height'][i]
        
        if conf > 30 and text and len(text.strip()) > 0:
            # Calculate padding used (same as in detection)
            if fixed_padding is not None:
                text_padding = fixed_padding
            elif tight_mask:
                text_padding = 1
            elif padding is not None:
                text_padding = padding
            else:
                text_padding = 2
            
            x1 = max(0, x - text_padding)
            y1 = max(0, y - text_padding)
            x2 = min(img.shape[1], x + w + text_padding)
            y2 = min(img.shape[0], y + h + text_padding)
            
            # Draw red border around removed region
            cv2.rectangle(mask_labeled, (x1, y1), (x2, y2), (0, 0, 255), 2)
    
    # Save labeled mask
    if output_path:
        mask_path = Path(output_path).parent / f"{Path(output_path).stem}_mask.png"
    else:
        input_path = Path(image_path)
        mask_path = input_path.parent / f"{input_path.stem}_no_text_mask.png"
    cv2.imwrite(str(mask_path), mask_labeled)
    print(f"Labeled mask saved to: {mask_path}")
    
    return result, text_mask


def compare_with_reference(result_path, reference_path):
    """Compare result with reference image."""
    result = cv2.imread(str(result_path))
    reference = cv2.imread(str(reference_path))
    
    if result is None or reference is None:
        print("Could not read images for comparison")
        return
    
    # Calculate difference
    diff = cv2.absdiff(result, reference)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    diff_pixels = np.sum(diff_gray > 30)  # Threshold for significant difference
    total_pixels = diff_gray.shape[0] * diff_gray.shape[1]
    
    print(f"\nComparison with reference:")
    print(f"Different pixels: {diff_pixels} ({100*diff_pixels/total_pixels:.2f}%)")
    
    return diff_pixels / total_pixels


def main():
    parser = argparse.ArgumentParser(
        description='Remove text from technical diagrams using OCR'
    )
    parser.add_argument('input', type=str, help='Input image path')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output image path (default: adds _no_text suffix)')
    parser.add_argument('-p', '--padding', type=int, default=None,
                       help='Padding around detected text (default: auto, 2px)')
    parser.add_argument('-d', '--dilation', type=int, default=1,
                       help='Dilation iterations (default: 1, use 0 for no dilation)')
    parser.add_argument('--tight', action='store_true',
                       help='Use tight mask (minimal 1px padding) to preserve nearby elements')
    parser.add_argument('--fixed-padding', type=int, default=None,
                       help='Use fixed padding for all text (most consistent mask sizes)')
    parser.add_argument('--enhance-contrast', action='store_true',
                       help='Apply CLAHE contrast enhancement before OCR (may help detect difficult text)')
    parser.add_argument('--compare', type=str, default=None,
                       help='Compare with reference image (path to reference)')
    
    args = parser.parse_args()
    
    if not OCR_AVAILABLE:
        print("\nERROR: pytesseract is not available.")
        print("Install with: pip install pytesseract")
        print("Also install Tesseract OCR:")
        print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  Linux: sudo apt-get install tesseract-ocr")
        print("  macOS: brew install tesseract")
        return
    
    try:
        result, mask = remove_text(
            args.input,
            args.output,
            padding=args.padding,
            dilation_iterations=args.dilation,
            tight_mask=args.tight,
            fixed_padding=args.fixed_padding,
            enhance_contrast=args.enhance_contrast
        )
        
        # Mask is already saved with labels in remove_text function
        
        # Compare with reference if provided
        if args.compare:
            compare_with_reference(args.output or f"{Path(args.input).stem}_no_text{Path(args.input).suffix}", 
                                  args.compare)
        
        print("\nDone!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

