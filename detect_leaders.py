"""
Detect and trace leader lines from text locations.
Starts from cleaned image (no text) and traces leaders to arrowheads.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
import json

try:
    import pytesseract
    from PIL import Image
    import os
    import platform
    
    # Auto-detect Tesseract
    if platform.system() == 'Windows':
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
    
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def detect_arrowhead(image, line_end_x, line_end_y, direction, search_radius=20):
    """
    Detect arrowhead at the end of a line.
    
    Args:
        image: Grayscale image
        line_end_x, line_end_y: End point of the line
        direction: Direction vector of the last line segment (dx, dy)
        search_radius: Radius to search for arrowhead
    
    Returns:
        Arrowhead points if found, None otherwise
    """
    h, w = image.shape
    
    # Normalize direction vector
    dx, dy = direction
    length = np.sqrt(dx**2 + dy**2)
    if length == 0:
        return None
    
    dx_norm = dx / length
    dy_norm = dy / length
    
    # Search in the direction of the line for arrowhead patterns
    # Arrowheads are typically triangular shapes pointing in the line direction
    
    # Create search region
    search_x1 = max(0, int(line_end_x - search_radius))
    search_y1 = max(0, int(line_end_y - search_radius))
    search_x2 = min(w, int(line_end_x + search_radius))
    search_y2 = min(h, int(line_end_y + search_radius))
    
    search_region = image[search_y1:search_y2, search_x1:search_x2]
    
    if search_region.size == 0:
        return None
    
    # Detect edges in search region
    edges = cv2.Canny(search_region, 50, 150)
    
    # Look for triangular patterns (arrowheads)
    # Arrowheads typically have 3-4 edges meeting at a point
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if 10 < area < 200:  # Reasonable arrowhead size
            # Check if contour is roughly triangular
            hull = cv2.convexHull(contour)
            if len(hull) >= 3 and len(hull) <= 6:  # Triangle to hexagon (arrowhead shapes)
                # Check if it's near the line end
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"]) + search_x1
                    cy = int(M["m01"] / M["m00"]) + search_y1
                    
                    # Check distance from line end
                    dist = np.sqrt((cx - line_end_x)**2 + (cy - line_end_y)**2)
                    if dist < search_radius:
                        return (cx, cy, contour)
    
    return None


def trace_line_from_point(image, start_x, start_y, max_length=300, step_size=2):
    """
    Trace a line starting from a point, following the line as it bends.
    
    Args:
        image: Grayscale image
        start_x, start_y: Starting point (near text location)
        max_length: Maximum length to trace
        step_size: Step size for tracing
    
    Returns:
        List of points along the traced line, or None if no line found
    """
    h, w = image.shape
    
    # Detect edges
    edges = cv2.Canny(image, 50, 150)
    
    # Start from the given point
    current_x, current_y = int(start_x), int(start_y)
    traced_points = [(current_x, current_y)]
    visited = set()
    visited.add((current_x, current_y))
    
    # Initial direction - search in all directions to find the line
    directions = [
        (1, 0), (-1, 0), (0, 1), (0, -1),  # Cardinal
        (1, 1), (-1, -1), (1, -1), (-1, 1)  # Diagonal
    ]
    
    # Find initial direction by looking for nearby edge pixels
    best_dir = None
    best_dist = float('inf')
    
    for dx, dy in directions:
        for dist in range(1, 20):
            test_x = current_x + dx * dist
            test_y = current_y + dy * dist
            if 0 <= test_x < w and 0 <= test_y < h:
                if edges[test_y, test_x] > 0:
                    if dist < best_dist:
                        best_dist = dist
                        best_dir = (dx, dy)
                    break
    
    if best_dir is None:
        return None
    
    # Trace the line
    direction = best_dir
    total_length = 0
    
    while total_length < max_length:
        # Look ahead in current direction
        found_next = False
        
        # Try current direction first
        for dist in range(step_size, step_size + 5):
            next_x = int(current_x + direction[0] * dist)
            next_y = int(current_y + direction[1] * dist)
            
            if 0 <= next_x < w and 0 <= test_y < h:
                if edges[next_y, next_x] > 0 and (next_x, next_y) not in visited:
                    current_x, current_y = next_x, next_y
                    traced_points.append((current_x, current_y))
                    visited.add((current_x, current_y))
                    total_length += dist
                    found_next = True
                    break
        
        if not found_next:
            # Try adjacent directions (line is bending)
            for angle_offset in [-45, -22.5, 22.5, 45, 67.5, 90]:
                angle_rad = np.arctan2(direction[1], direction[0]) + np.radians(angle_offset)
                new_dx = int(np.cos(angle_rad) * step_size)
                new_dy = int(np.sin(angle_rad) * step_size)
                
                test_x = current_x + new_dx
                test_y = current_y + new_dy
                
                if 0 <= test_x < w and 0 <= test_y < h:
                    if edges[test_y, test_x] > 0 and (test_x, test_y) not in visited:
                        direction = (new_dx / step_size, new_dy / step_size)
                        current_x, current_y = test_x, test_y
                        traced_points.append((current_x, current_y))
                        visited.add((current_x, current_y))
                        total_length += step_size
                        found_next = True
                        break
        
        if not found_next:
            break  # Line ended
    
    return traced_points if len(traced_points) > 5 else None


def find_leaders_from_text_locations(cleaned_image_path, text_locations=None, ocr_data_path=None):
    """
    Find leader lines starting from text locations.
    
    Args:
        cleaned_image_path: Path to cleaned image (no text)
        text_locations: List of (x, y, w, h) tuples for text locations
        ocr_data_path: Optional path to saved OCR data JSON
    
    Returns:
        List of leader line data (points, arrowhead location)
    """
    # Read cleaned image
    img = cv2.imread(str(cleaned_image_path))
    if img is None:
        raise ValueError(f"Could not read image: {cleaned_image_path}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Get text locations
    if text_locations is None:
        if ocr_data_path and Path(ocr_data_path).exists():
            with open(ocr_data_path, 'r') as f:
                ocr_data = json.load(f)
            text_locations = [
                (ocr_data['left'][i], ocr_data['top'][i], 
                 ocr_data['width'][i], ocr_data['height'][i])
                for i in range(len(ocr_data['text']))
            ]
        else:
            # Try to detect text locations from cleaned image using OCR
            if not OCR_AVAILABLE:
                raise ValueError("Need text locations or OCR data")
            
            print("Detecting text locations from cleaned image...")
            pil_image = Image.fromarray(gray)
            ocr_data = pytesseract.image_to_data(
                pil_image, output_type=pytesseract.Output.DICT, config='--psm 11'
            )
            
            text_locations = []
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])
                if conf > 50 and text:
                    text_locations.append((
                        ocr_data['left'][i],
                        ocr_data['top'][i],
                        ocr_data['width'][i],
                        ocr_data['height'][i]
                    ))
    
    print(f"Found {len(text_locations)} text locations to search for leaders")
    
    # For each text location, search for leader lines
    leaders = []
    
    for i, (tx, ty, tw, th) in enumerate(text_locations):
        print(f"\nProcessing text location {i+1}: ({tx}, {ty}) size {tw}x{th}")
        
        # Search around text location for line starts
        # Leaders typically start near the edges of text
        # Use multiple search points with small offsets to find line starts
        search_points = []
        for offset in [0, 2, 4, -2, -4]:
            search_points.extend([
                (tx + tw + offset, ty + th // 2),  # Right edge
                (tx + tw // 2, ty + th + offset),  # Bottom edge
                (tx + offset, ty + th // 2),        # Left edge
                (tx + tw // 2, ty + offset),        # Top edge
            ])
        
        for start_x, start_y in search_points:
            # Trace line from this point
            traced_points = trace_line_from_point(gray, start_x, start_y)
            
            if traced_points and len(traced_points) > 10:  # Minimum length for a leader
                # Filter: Leaders should be relatively short (not structural elements)
                total_length = 0
                for j in range(len(traced_points) - 1):
                    p1 = traced_points[j]
                    p2 = traced_points[j + 1]
                    total_length += np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                
                # Leaders are typically 50-300 pixels long
                if total_length < 50 or total_length > 400:
                    continue
                
                # Check for arrowhead at the end
                arrowhead = None
                if len(traced_points) >= 2:
                    # Calculate direction of last segment
                    last_point = traced_points[-1]
                    second_last = traced_points[-2]
                    direction = (last_point[0] - second_last[0], last_point[1] - second_last[1])
                    
                    arrowhead = detect_arrowhead(gray, last_point[0], last_point[1], direction)
                
                # Prefer leaders with arrowheads, but accept without if reasonable
                if arrowhead or total_length < 200:  # Short lines might not have visible arrowheads
                    leaders.append({
                        'text_location': (tx, ty, tw, th),
                        'start_point': (start_x, start_y),
                        'points': traced_points,
                        'arrowhead': arrowhead,
                        'length': total_length
                    })
                    print(f"  Found leader with {len(traced_points)} points, length={total_length:.1f}px")
                    break  # Found a leader for this text, move to next
    
    return leaders, img


def visualize_leaders(image, leaders, output_path):
    """
    Visualize detected leaders in red.
    
    Args:
        image: Original image
        leaders: List of leader data
        output_path: Path to save visualization
    """
    vis_img = image.copy()
    
    for leader in leaders:
        points = leader['points']
        arrowhead = leader['arrowhead']
        
        # Draw leader line in red
        if len(points) > 1:
            pts = np.array(points, dtype=np.int32)
            cv2.polylines(vis_img, [pts], False, (0, 0, 255), 2)
        
        # Draw arrowhead in bright red
        if arrowhead:
            cx, cy, contour = arrowhead
            # Draw contour
            contour_shifted = contour.copy()
            for pt in contour_shifted:
                pt[0][0] += cx - contour.shape[0] // 2
                pt[0][1] += cy - contour.shape[1] // 2
            cv2.drawContours(vis_img, [contour_shifted], -1, (0, 0, 255), 3)
            cv2.circle(vis_img, (cx, cy), 5, (0, 0, 255), -1)
        
        # Highlight start point (near text)
        start_x, start_y = leader['start_point']
        cv2.circle(vis_img, (start_x, start_y), 5, (0, 255, 0), -1)  # Green for start
    
    cv2.imwrite(str(output_path), vis_img)
    print(f"\nSaved leader visualization to: {output_path}")
    
    return vis_img


def main():
    parser = argparse.ArgumentParser(
        description='Detect and trace leader lines from text locations'
    )
    parser.add_argument('cleaned_image', type=str,
                       help='Path to cleaned image (no text)')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output image path (default: adds _leaders suffix)')
    parser.add_argument('--ocr-data', type=str, default=None,
                       help='Path to JSON file with OCR data (text locations)')
    parser.add_argument('--original', type=str, default=None,
                       help='Path to original image (for getting text locations via OCR)')
    
    args = parser.parse_args()
    
    # Get text locations
    text_locations = None
    if args.ocr_data:
        # Load from JSON
        with open(args.ocr_data, 'r') as f:
            ocr_data = json.load(f)
        text_locations = [
            (ocr_data['left'][i], ocr_data['top'][i],
             ocr_data['width'][i], ocr_data['height'][i])
            for i in range(len(ocr_data['text']))
        ]
    elif args.original:
        # Detect from original image
        print("Detecting text locations from original image...")
        img_orig = cv2.imread(args.original)
        gray_orig = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
        pil_orig = Image.fromarray(gray_orig)
        ocr_data = pytesseract.image_to_data(
            pil_orig, output_type=pytesseract.Output.DICT, config='--psm 11'
        )
        text_locations = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            if conf > 50 and text:
                text_locations.append((
                    ocr_data['left'][i],
                    ocr_data['top'][i],
                    ocr_data['width'][i],
                    ocr_data['height'][i]
                ))
    
    # Detect leaders
    leaders, img = find_leaders_from_text_locations(
        args.cleaned_image,
        text_locations=text_locations,
        ocr_data_path=args.ocr_data
    )
    
    print(f"\nDetected {len(leaders)} leader lines")
    
    # Visualize
    if args.output is None:
        input_path = Path(args.cleaned_image)
        output_path = input_path.parent / f"{input_path.stem}_leaders{input_path.suffix}"
    else:
        output_path = args.output
    
    visualize_leaders(img, leaders, output_path)
    
    print("Done!")


if __name__ == '__main__':
    main()

