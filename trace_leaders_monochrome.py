"""
Trace leader lines from red marker points in monochrome image.
Starts from manually marked red squares and traces lines to arrowheads.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse


def find_red_markers(image):
    """
    Find red square markers in the image.
    Looks for square/rectangular red regions.
    
    Args:
        image: BGR image
    
    Returns:
        List of (x, y) coordinates of red markers
    """
    # Convert to HSV for better color detection
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Define red color range (red wraps around 180 in HSV)
    # Lower red
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    # Upper red
    lower_red2 = np.array([170, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    
    # Create mask for red
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)
    
    # Find contours of red regions
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    markers = []
    candidate_markers = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter for square/rectangular markers
        # Check aspect ratio (should be roughly square, 0.6 to 1.6)
        aspect_ratio = w / h if h > 0 else 0
        
        # Check if it's roughly rectangular (solidity)
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        
        # Red squares should be small to medium sized, roughly square, and solid
        # Criteria for actual square markers (user manually added)
        if (50 < area < 2000 and 
            0.4 < aspect_ratio < 2.5 and  # Allow some rectangular variation
            solidity > 0.65):  # At least 65% solid (rectangular)
            center_x = x + w // 2
            center_y = y + h // 2
            candidate_markers.append({
                'center': (center_x, center_y),
                'area': area,
                'size': (w, h),
                'aspect': aspect_ratio,
                'solidity': solidity
            })
    
    # If we found multiple candidates, prefer the most square-like ones
    # Sort by how square they are (aspect ratio closest to 1.0) and solidity
    if candidate_markers:
        # Filter further: prefer markers that are more square (aspect near 1.0)
        # and have reasonable size (not too large, which might be other red elements)
        square_candidates = [m for m in candidate_markers if 0.4 < m['aspect'] < 2.5 and 50 < m['area'] < 1500]
        
        if square_candidates:
            square_candidates.sort(key=lambda m: (abs(m['aspect'] - 1.0), -m['solidity']))
            # Take top 2 most square-like markers
            for candidate in square_candidates[:2]:
                center_x, center_y = candidate['center']
                markers.append((center_x, center_y))
                print(f"Found red square marker at ({center_x}, {center_y}) size={candidate['size'][0]}x{candidate['size'][1]} area={candidate['area']:.0f} aspect={candidate['aspect']:.2f}")
        else:
            # Fallback: use all candidates if no square ones found
            candidate_markers.sort(key=lambda m: (abs(m['aspect'] - 1.0), -m['solidity']))
            for candidate in candidate_markers[:2]:
                center_x, center_y = candidate['center']
                markers.append((center_x, center_y))
                print(f"Found red marker at ({center_x}, {center_y}) size={candidate['size'][0]}x{candidate['size'][1]} area={candidate['area']:.0f} aspect={candidate['aspect']:.2f}")
    
    return markers


def convert_to_monochrome(image):
    """
    Convert image to true black and white (monochrome).
    
    Args:
        image: BGR or grayscale image
    
    Returns:
        Binary black and white image (0 or 255)
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Use Otsu's thresholding for automatic threshold selection
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary


def get_line_direction(p1, p2):
    """Get normalized direction vector from p1 to p2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = np.sqrt(dx**2 + dy**2)
    if length == 0:
        return (0, 0)
    return (dx / length, dy / length)


def show_tracing_step(binary_image, current_x, current_y, next_x, next_y, direction, 
                     traced_points, zoom=5, is_turn=False, angle=0, step_num=0):
    """
    Show zoomed-in visualization of tracing step and wait for user input.
    Saves visualization to file and prompts user for input.
    
    Args:
        binary_image: Binary image
        current_x, current_y: Current position
        next_x, next_y: Proposed next position
        direction: Direction vector
        traced_points: All traced points so far
        zoom: Zoom factor (default 5x)
        is_turn: True if this is a turn, False if straight
        angle: Angle of turn if is_turn is True
        step_num: Step number for filename
    
    Returns:
        User input: 'y', 'n', 'x', or key code
    """
    h, w = binary_image.shape
    
    # Create zoomed view (5x)
    view_size = 100  # Size of view window in original image
    zoom_size = view_size * zoom
    
    # Center view on current position
    view_x1 = max(0, current_x - view_size // 2)
    view_y1 = max(0, current_y - view_size // 2)
    view_x2 = min(w, current_x + view_size // 2)
    view_y2 = min(h, current_y + view_size // 2)
    
    # Extract region
    region = binary_image[view_y1:view_y2, view_x1:view_x2].copy()
    
    # Convert to BGR for colored overlay
    vis_region = cv2.cvtColor(region, cv2.COLOR_GRAY2BGR)
    
    # Adjust coordinates to region space
    region_current_x = current_x - view_x1
    region_current_y = current_y - view_y1
    region_next_x = next_x - view_x1
    region_next_y = next_y - view_y1
    
    # Draw traced path so far (in blue)
    if len(traced_points) > 1:
        region_traced = []
        for px, py in traced_points[-20:]:  # Last 20 points
            rx = px - view_x1
            ry = py - view_y1
            if 0 <= rx < region.shape[1] and 0 <= ry < region.shape[0]:
                region_traced.append((rx, ry))
        
        if len(region_traced) > 1:
            pts = np.array(region_traced, dtype=np.int32)
            cv2.polylines(vis_region, [pts], False, (255, 0, 0), 1)
    
    # Draw current position (yellow circle)
    cv2.circle(vis_region, (region_current_x, region_current_y), 3, (0, 255, 255), -1)
    
    # Draw proposed direction (green arrow)
    cv2.arrowedLine(vis_region, 
                    (region_current_x, region_current_y),
                    (region_next_x, region_next_y),
                    (0, 255, 0), 2, tipLength=0.3)
    
    # Draw next position (green circle)
    cv2.circle(vis_region, (region_next_x, region_next_y), 3, (0, 255, 0), -1)
    
    # Zoom the region
    vis_zoomed = cv2.resize(vis_region, (zoom_size, zoom_size), interpolation=cv2.INTER_NEAREST)
    
    # Add text overlay
    status_text = f"Turn {angle:.0f}deg" if is_turn else "Straight"
    cv2.putText(vis_zoomed, status_text, (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(vis_zoomed, "Y=Yes, N=No, X=Exit", (10, zoom_size - 20),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(vis_zoomed, f"Step {len(traced_points)}", (10, 60),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Save visualization to file
    debug_filename = f"trace_debug_step_{step_num:04d}.png"
    cv2.imwrite(debug_filename, vis_zoomed)
    
    # Print status and prompt user
    print(f"\n{'='*60}")
    print(f"Step {len(traced_points)}: {status_text}")
    print(f"Current: ({current_x}, {current_y}) -> Next: ({next_x}, {next_y})")
    print(f"Visualization saved to: {debug_filename}")
    print(f"{'='*60}")
    print("Press Y to accept, N to reject, X to exit: ", end='', flush=True)
    
    # Get user input
    try:
        user_input = input().strip().lower()
        if user_input == 'y':
            return 'y'
        elif user_input == 'n':
            return 'n'
        elif user_input == 'x':
            return 'x'
        else:
            print(f"Invalid input '{user_input}', treating as 'n'")
            return 'n'
    except (EOFError, KeyboardInterrupt):
        return 'x'


def find_green_dots(image):
    """
    Find green dots in the image (marked arrow tips).
    
    Args:
        image: BGR image
    
    Returns:
        List of (x, y) coordinates of green dots
    """
    # Convert to HSV for better color detection
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Define green color range
    lower_green = np.array([40, 50, 50])
    upper_green = np.array([80, 255, 255])
    
    # Create mask for green
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # Find contours of green regions
    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    green_dots = []
    for contour in contours:
        area = cv2.contourArea(contour)
        # Green dots should be small
        if 5 < area < 500:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                green_dots.append((cx, cy))
                print(f"Found green dot (arrow tip) at ({cx}, {cy})")
    
    return green_dots


def analyze_neighborhood(binary_image, x, y, scale=3):
    """
    Analyze a scaled 9-point neighborhood around a point to find line directions.
    
    Args:
        binary_image: Binary image (0 = black line, 255 = white background)
        x, y: Center point
        scale: Scale factor for neighborhood (default 3, so 3x3 = 9 points at scale 1)
    
    Returns:
        List of directions (dx, dy) normalized, representing where lines are found
    """
    h, w = binary_image.shape
    directions = []
    
    # 9-point neighborhood: 8 directions around center
    # Directions: N, NE, E, SE, S, SW, W, NW
    offsets = [
        (0, -scale),      # North
        (scale, -scale),  # Northeast
        (scale, 0),       # East
        (scale, scale),   # Southeast
        (0, scale),       # South
        (-scale, scale),  # Southwest
        (-scale, 0),      # West
        (-scale, -scale)  # Northwest
    ]
    
    for dx, dy in offsets:
        test_x = int(x + dx)
        test_y = int(y + dy)
        
        if 0 <= test_x < w and 0 <= test_y < h:
            # Check if this pixel is on a line (black)
            if binary_image[test_y, test_x] < 127:
                # Normalize direction
                length = np.sqrt(dx*dx + dy*dy)
                if length > 0:
                    directions.append((dx / length, dy / length))
    
    return directions


def find_nearest_line_point(binary_image, x, y, search_radius=20):
    """
    Find the nearest line pixel in the neighborhood of a given point.
    Used when the starting point is not directly on a line.
    
    Args:
        binary_image: Binary image (0 = black line, 255 = white background)
        x, y: Center point to search around
        search_radius: Maximum distance to search
    
    Returns:
        (nearest_x, nearest_y) if found, None otherwise
    """
    h, w = binary_image.shape
    x, y = int(x), int(y)
    
    # Ensure we're working with black lines on white background
    if binary_image[y, x] > 127:
        work_image = 255 - binary_image
    else:
        work_image = binary_image.copy()
    
    min_dist = float('inf')
    nearest_point = None
    
    # Search in expanding circles
    for radius in range(1, search_radius + 1):
        # Check all points in a square around the center
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                # Only check points on the circle perimeter (for efficiency)
                dist = np.sqrt(dx*dx + dy*dy)
                if radius - 0.5 <= dist <= radius + 0.5:
                    test_x = x + dx
                    test_y = y + dy
                    
                    if 0 <= test_x < w and 0 <= test_y < h:
                        # Check if this pixel is on a line (black)
                        if work_image[test_y, test_x] < 127:
                            # Check if this point has neighbors (is part of a line, not isolated)
                            has_neighbors = False
                            for n_dy in [-1, 0, 1]:
                                for n_dx in [-1, 0, 1]:
                                    if n_dx == 0 and n_dy == 0:
                                        continue
                                    n_x = test_x + n_dx
                                    n_y = test_y + n_dy
                                    if 0 <= n_x < w and 0 <= n_y < h:
                                        if work_image[n_y, n_x] < 127:
                                            has_neighbors = True
                                            break
                                if has_neighbors:
                                    break
                            
                            if has_neighbors and dist < min_dist:
                                min_dist = dist
                                nearest_point = (test_x, test_y)
        
        # If we found a point, return it (closest one)
        if nearest_point:
            print(f"  Starting point ({x}, {y}) not on line, found nearest line point at {nearest_point} (distance: {min_dist:.1f})")
            return nearest_point
    
    return None


def trace_line_monochrome(binary_image, start_x, start_y, max_length=500, interactive=False, scale=3):
    """
    Trace a line in monochrome image using neighborhood-based approach.
    
    Algorithm:
    1. Use scaled 9-point neighborhood to find line directions
    2. Exclude the direction we came from
    3. Check opposite direction first (continue straight)
    4. If opposite doesn't work, look for turns
    
    Args:
        binary_image: Binary black and white image (0 = black, 255 = white)
        start_x, start_y: Starting point
        max_length: Maximum length to trace
        interactive: If True, show step-by-step visualization with keyboard control
        scale: Scale factor for neighborhood (default 3)
    
    Returns:
        List of points along the traced line
    """
    h, w = binary_image.shape
    
    # Ensure we're working with black lines on white background
    # Check if start point is on a line (black pixel)
    if binary_image[int(start_y), int(start_x)] > 127:
        # White pixel, invert image
        work_image = 255 - binary_image
    else:
        work_image = binary_image.copy()
    
    # Start from the given point
    current_x, current_y = int(start_x), int(start_y)
    traced_points = [(current_x, current_y)]
    visited = set()
    visited.add((current_x, current_y))
    
    # Initial direction - use neighborhood to find line direction
    initial_directions = analyze_neighborhood(work_image, current_x, current_y, scale)
    if not initial_directions:
        return None
    
    # For initial direction, pick the one with most line pixels ahead
    best_dir = None
    best_score = 0
    for dx, dy in initial_directions:
        score = 0
        for dist in range(1, 10):
            test_x = int(current_x + dx * dist)
            test_y = int(current_y + dy * dist)
            if 0 <= test_x < w and 0 <= test_y < h:
                if work_image[test_y, test_x] < 127:
                    score += 1
                else:
                    break
        if score > best_score:
            best_score = score
            best_dir = (dx, dy)
    
    if best_dir is None:
        return None
    
    direction = best_dir
    previous_direction = None  # Track where we came from
    total_length = 0
    consecutive_failures = 0
    max_failures = 5
    
    while total_length < max_length and consecutive_failures < max_failures:
        found_next = False
        
        # Analyze neighborhood to find available directions
        available_directions = analyze_neighborhood(work_image, current_x, current_y, scale)
        
        if not available_directions:
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                break
            continue
        
        # Exclude the direction we came from
        if previous_direction is not None:
            # Remove directions too similar to where we came from
            filtered_directions = []
            for dx, dy in available_directions:
                # Check angle difference from previous direction
                dot_product = dx * previous_direction[0] + dy * previous_direction[1]
                # If dot product is positive, it's in similar direction (coming from)
                if dot_product < 0.3:  # Allow some tolerance, but exclude opposite
                    filtered_directions.append((dx, dy))
            
            if filtered_directions:
                available_directions = filtered_directions
        
        # Priority 1: Check opposite direction (continue straight)
        # Due to skeletonization, the continuation can be in any of 3 pixels opposite
        # where we came from. In 8-neighborhood, check exact opposite and adjacent opposites.
        if previous_direction is not None:
            # We came from previous_direction, so check pixels opposite to that
            # In 8-neighborhood: if we came from direction (dx, dy), check:
            # 1. Exact opposite: (-dx, -dy)
            # 2. Adjacent opposites: rotate ±45 degrees from opposite
            
            prev_dx, prev_dy = previous_direction
            
            # Get the 8-neighborhood offsets for opposite direction
            # Map direction to nearest 8-direction, then get its 3 opposite neighbors
            # 8 directions: N(0,-1), NE(1,-1), E(1,0), SE(1,1), S(0,1), SW(-1,1), W(-1,0), NW(-1,-1)
            
            # Find which 8-direction we came from (closest match)
            angles_8dir = [np.arctan2(-1, 0), np.arctan2(-1, 1), np.arctan2(0, 1), np.arctan2(1, 1),
                          np.arctan2(1, 0), np.arctan2(1, -1), np.arctan2(0, -1), np.arctan2(-1, -1)]
            offsets_8dir = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
            
            prev_angle = np.arctan2(prev_dy, prev_dx)
            closest_idx = min(range(8), key=lambda i: abs(angles_8dir[i] - prev_angle))
            
            # Get opposite direction and its two neighbors (3 pixels total)
            opposite_idx = (closest_idx + 4) % 8  # Opposite in 8-direction
            candidate_indices = [
                opposite_idx,  # Exact opposite
                (opposite_idx - 1) % 8,  # One direction clockwise
                (opposite_idx + 1) % 8,  # One direction counter-clockwise
            ]
            
            # Check each of the 3 candidate pixels
            for idx in candidate_indices:
                offset_dx, offset_dy = offsets_8dir[idx]
                test_x = int(current_x + offset_dx * scale)
                test_y = int(current_y + offset_dy * scale)
                
                if 0 <= test_x < w and 0 <= test_y < h:
                    if work_image[test_y, test_x] < 127 and (test_x, test_y) not in visited:
                        # Found a valid continuation
                        dist = scale
                        
                        # Calculate direction for this move
                        new_dx = offset_dx / np.sqrt(offset_dx*offset_dx + offset_dy*offset_dy) if (offset_dx != 0 or offset_dy != 0) else 0
                        new_dy = offset_dy / np.sqrt(offset_dx*offset_dx + offset_dy*offset_dy) if (offset_dx != 0 or offset_dy != 0) else 0
                        
                        # Interactive mode
                        if interactive:
                            user_choice = show_tracing_step(work_image, current_x, current_y, 
                                                           test_x, test_y, (new_dx, new_dy), 
                                                           traced_points, zoom=5, 
                                                           step_num=len(traced_points))
                            if user_choice == 'x' or user_choice == ord('x'):
                                print("User exited tracing")
                                return traced_points
                            elif user_choice == 'y' or user_choice == ord('y'):
                                # Accept
                                previous_direction = (-new_dx, -new_dy)  # Where we came from
                                direction = (new_dx, new_dy)
                                current_x, current_y = test_x, test_y
                                traced_points.append((current_x, current_y))
                                visited.add((current_x, current_y))
                                total_length += dist
                                consecutive_failures = 0
                                found_next = True
                                break
                            elif user_choice == 'n' or user_choice == ord('n'):
                                # Reject, try next candidate
                                continue
                        else:
                            # Non-interactive: accept first valid
                            previous_direction = (-new_dx, -new_dy)
                            direction = (new_dx, new_dy)
                            current_x, current_y = test_x, test_y
                            traced_points.append((current_x, current_y))
                            visited.add((current_x, current_y))
                            total_length += dist
                            consecutive_failures = 0
                            found_next = True
                            break
                
                if found_next:
                    break
        
        # Priority 2: If opposite didn't work, try other directions (turns)
        if not found_next:
            # Sort directions by how well they continue the current direction
            scored_directions = []
            current_angle = np.arctan2(direction[1], direction[0]) if direction else 0
            
            for dx, dy in available_directions:
                dir_angle = np.arctan2(dy, dx)
                angle_diff = abs(dir_angle - current_angle)
                if angle_diff > np.pi:
                    angle_diff = 2 * np.pi - angle_diff
                
                # Score: prefer smaller angle changes (smooth turns)
                score = 1.0 / (1.0 + angle_diff)
                scored_directions.append((score, dx, dy))
            
            # Sort by score (best first)
            scored_directions.sort(reverse=True, key=lambda x: x[0])
            
            # Try directions in order
            for score, dx, dy in scored_directions:
                # Find first valid point in this direction
                for dist in range(1, scale + 2):
                    test_x = int(current_x + dx * dist)
                    test_y = int(current_y + dy * dist)
                    if 0 <= test_x < w and 0 <= test_y < h:
                        if work_image[test_y, test_x] < 127 and (test_x, test_y) not in visited:
                            angle_diff_deg = np.degrees(np.arctan2(dy, dx) - current_angle)
                            if angle_diff_deg > 180:
                                angle_diff_deg -= 360
                            elif angle_diff_deg < -180:
                                angle_diff_deg += 360
                            
                            # Interactive mode
                            if interactive:
                                user_choice = show_tracing_step(work_image, current_x, current_y,
                                                               test_x, test_y, (dx, dy),
                                                               traced_points, zoom=5,
                                                               is_turn=True, angle=angle_diff_deg,
                                                               step_num=len(traced_points))
                                if user_choice == 'x' or user_choice == ord('x'):
                                    print("User exited tracing")
                                    return traced_points
                                elif user_choice == 'y' or user_choice == ord('y'):
                                    # Accept turn
                                    previous_direction = (-dx, -dy)
                                    direction = (dx, dy)
                                    current_x, current_y = test_x, test_y
                                    traced_points.append((current_x, current_y))
                                    visited.add((current_x, current_y))
                                    total_length += dist
                                    consecutive_failures = 0
                                    found_next = True
                                    break
                                elif user_choice == 'n' or user_choice == ord('n'):
                                    # Reject, try next direction
                                    continue
                            else:
                                # Non-interactive: accept first valid
                                previous_direction = (-dx, -dy)
                                direction = (dx, dy)
                                current_x, current_y = test_x, test_y
                                traced_points.append((current_x, current_y))
                                visited.add((current_x, current_y))
                                total_length += dist
                                consecutive_failures = 0
                                found_next = True
                                break
                
                if found_next:
                    break
        
        if not found_next:
            consecutive_failures += 1
    
    return traced_points if len(traced_points) > 5 else None


def handle_fork(traced_points, binary_image, start_x, start_y):
    """
    Handle forks in the line (like at the top where lines branch).
    When a fork is detected, choose the branch that continues the current direction best.
    
    Args:
        traced_points: Current traced points
        binary_image: Binary image
        start_x, start_y: Original start point
    
    Returns:
        Traced points with fork handling
    """
    if len(traced_points) < 10:
        return traced_points
    
    h, w = binary_image.shape
    
    # Invert if needed
    if binary_image[int(start_y), int(start_x)] > 127:
        work_image = 255 - binary_image
    else:
        work_image = binary_image.copy()
    
    # Check for forks by looking at recent points
    # A fork occurs when multiple paths are available
    fork_threshold = 20  # Look back this many points
    
    if len(traced_points) > fork_threshold:
        # Check recent points for forks
        recent_points = traced_points[-fork_threshold:]
        
        # Look for points where multiple directions are possible
        for i in range(len(recent_points) - 5, len(recent_points)):
            if i < 0:
                continue
            
            px, py = recent_points[i]
            
            # Count available directions (unvisited black pixels)
            available_directions = []
            for angle in range(0, 360, 15):  # Check every 15 degrees
                rad = np.radians(angle)
                test_x = int(px + np.cos(rad) * 3)
                test_y = int(py + np.sin(rad) * 3)
                
                if 0 <= test_x < w and 0 <= test_y < h:
                    if work_image[test_y, test_x] < 127:
                        # Check if this direction continues the line
                        if i > 0:
                            prev_px, prev_py = recent_points[i-1]
                            dir_to_point = (test_x - px, test_y - py)
                            dir_from_prev = (px - prev_px, py - prev_py)
                            
                            # Prefer directions that continue the current path
                            dot_product = dir_to_point[0] * dir_from_prev[0] + dir_to_point[1] * dir_from_prev[1]
                            if dot_product > 0:  # Same general direction
                                available_directions.append((test_x, test_y, angle))
            
            # If multiple directions available, we're at a fork
            # Choose the one that best continues the current direction
            if len(available_directions) > 1:
                # Use the direction that's closest to current direction
                if i > 0:
                    prev_px, prev_py = recent_points[i-1]
                    current_dir = (px - prev_px, py - prev_py)
                    current_angle = np.arctan2(current_dir[1], current_dir[0])
                    
                    best_dir = None
                    best_angle_diff = float('inf')
                    
                    for test_x, test_y, angle in available_directions:
                        angle_diff = abs(np.radians(angle) - current_angle)
                        if angle_diff > np.pi:
                            angle_diff = 2 * np.pi - angle_diff
                        
                        if angle_diff < best_angle_diff:
                            best_angle_diff = angle_diff
                            best_dir = (test_x, test_y)
                    
                    # Continue from best direction
                    if best_dir:
                        # The tracing algorithm should handle this, but we can help
                        pass
    
    return traced_points


def detect_arrowhead_monochrome(binary_image, line_end_x, line_end_y, direction, search_radius=15):
    """
    Detect arrowhead at the end of a traced line in monochrome image.
    """
    h, w = binary_image.shape
    
    # Invert if needed
    if binary_image[int(line_end_y), int(line_end_x)] > 127:
        work_image = 255 - binary_image
    else:
        work_image = binary_image.copy()
    
    # Search region around line end
    search_x1 = max(0, int(line_end_x - search_radius))
    search_y1 = max(0, int(line_end_y - search_radius))
    search_x2 = min(w, int(line_end_x + search_radius))
    search_y2 = min(h, int(line_end_y + search_radius))
    
    search_region = work_image[search_y1:search_y2, search_x1:search_x2]
    
    if search_region.size == 0:
        return None
    
    # Look for arrowhead pattern (triangular shape)
    # Arrowheads are typically small dark regions at line ends
    contours, _ = cv2.findContours(search_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if 5 < area < 150:  # Small region
            # Check if it's roughly triangular
            hull = cv2.convexHull(contour)
            if 3 <= len(hull) <= 6:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"]) + search_x1
                    cy = int(M["m01"] / M["m00"]) + search_y1
                    
                    dist = np.sqrt((cx - line_end_x)**2 + (cy - line_end_y)**2)
                    if dist < search_radius:
                        return (cx, cy, contour)
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Trace leader lines from red markers in monochrome image'
    )
    parser.add_argument('input_image', type=str,
                       help='Input image with red markers (BMP or JPG)')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output image path (default: adds _traced suffix)')
    parser.add_argument('--start-points', type=str, default=None,
                       help='Manual start points as "x1,y1 x2,y2" (overrides red marker detection)')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive debugging mode: step through tracing with Y/N/X keys')
    
    args = parser.parse_args()
    
    # Read image
    img = cv2.imread(str(args.input_image))
    if img is None:
        raise ValueError(f"Could not read image: {args.input_image}")
    
    print(f"Processing image: {args.input_image}")
    print(f"Image size: {img.shape[1]}x{img.shape[0]} pixels")
    
    # Find red markers or use manual points
    if args.start_points:
        # Parse manual points
        points_str = args.start_points.split()
        start_points = []
        for pt_str in points_str:
            x, y = map(int, pt_str.split(','))
            start_points.append((x, y))
        print(f"Using manual start points: {start_points}")
    else:
        # Detect red markers
        start_points = find_red_markers(img)
        if not start_points:
            print("Warning: No red markers found. Use --start-points to specify manually.")
            return
    
    # Convert to monochrome (black and white)
    print("\nConverting to monochrome...")
    binary = convert_to_monochrome(img)
    
    # Create output image (keep monochrome but convert to BGR for colored overlay)
    output_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    
    # Trace lines from each start point
    all_leaders = []
    
    for i, (start_x, start_y) in enumerate(start_points):
        print(f"\nTracing from point {i+1}: ({start_x}, {start_y})")
        
        # Try to trace from the given point
        traced_points = trace_line_monochrome(binary, start_x, start_y, interactive=args.interactive)
        
        # If no line detected, search neighborhood for nearest line point
        if not traced_points or len(traced_points) <= 5:
            print(f"  No line detected from ({start_x}, {start_y}), searching neighborhood...")
            nearest_point = find_nearest_line_point(binary, start_x, start_y, search_radius=20)
            
            if nearest_point:
                new_start_x, new_start_y = nearest_point
                print(f"  Retrying from nearest line point: ({new_start_x}, {new_start_y})")
                traced_points = trace_line_monochrome(binary, new_start_x, new_start_y, interactive=args.interactive)
                # Update start point for display
                start_x, start_y = new_start_x, new_start_y
            else:
                print(f"  No line found in neighborhood of ({start_x}, {start_y})")
        
        if traced_points and len(traced_points) > 5:
            # Handle forks if needed
            traced_points = handle_fork(traced_points, binary, start_x, start_y)
            
            all_leaders.append({
                'start': (start_x, start_y),
                'points': traced_points,
                'arrowhead': None  # Skip arrowhead detection for now
            })
            
            print(f"  Traced {len(traced_points)} points")
            
            # Draw traced line in red
            if len(traced_points) > 1:
                pts = np.array(traced_points, dtype=np.int32)
                cv2.polylines(output_img, [pts], False, (0, 0, 255), 2)
            
            # Mark start point in green
            cv2.circle(output_img, (start_x, start_y), 5, (0, 255, 0), -1)
    
    # Save output
    if args.output is None:
        input_path = Path(args.input_image)
        output_path = input_path.parent / f"{input_path.stem}_traced{input_path.suffix}"
    else:
        output_path = args.output
    
    cv2.imwrite(str(output_path), output_img)
    print(f"\nSaved traced leaders to: {output_path}")
    print(f"Detected {len(all_leaders)} leader lines")
    
    # Also save monochrome version
    mono_path = Path(output_path).parent / f"{Path(output_path).stem}_monochrome.png"
    cv2.imwrite(str(mono_path), binary)
    print(f"Saved monochrome image to: {mono_path}")
    
    # Close any open windows (if GUI is available)
    if args.interactive:
        try:
            cv2.destroyAllWindows()
        except:
            pass  # GUI not available, ignore


if __name__ == '__main__':
    main()

