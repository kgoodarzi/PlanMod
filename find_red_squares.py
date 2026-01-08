"""Find and visualize all red regions to identify square markers."""
import cv2
import numpy as np

img = cv2.imread('IMG_9236_Leaders_Marked_Manually.bmp')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Red color range
lower_red1 = np.array([0, 50, 50])
upper_red1 = np.array([10, 255, 255])
lower_red2 = np.array([170, 50, 50])
upper_red2 = np.array([180, 255, 255])

mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
red_mask = cv2.bitwise_or(mask1, mask2)

contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Draw all red regions with labels
vis = img.copy()
print("All red regions:")
for i, contour in enumerate(contours):
    area = cv2.contourArea(contour)
    if area > 20:
        x, y, w, h = cv2.boundingRect(contour)
        aspect = w / h if h > 0 else 0
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        
        center_x = x + w // 2
        center_y = y + h // 2
        
        # Draw rectangle
        cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(vis, f"{i}", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        print(f"  {i}: center=({center_x},{center_y}) size={w}x{h} area={area:.0f} aspect={aspect:.2f} solidity={solidity:.2f}")

cv2.imwrite('red_regions_visualized.jpg', vis)
print("\nSaved visualization to: red_regions_visualized.jpg")

