"""Check LEFT detection details to understand the extra space."""
import cv2
from PIL import Image
import pytesseract
import os
import platform
import numpy as np

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

img = cv2.imread('IMG_9236.JPEG')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Get OCR data
pil = Image.fromarray(gray)
data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config='--psm 11')

print("LEFT detection details:")
for i in range(len(data['text'])):
    text = data['text'][i].strip()
    conf = int(data['conf'][i])
    if 'LEFT' in text.upper() and conf > 0:
        x = data['left'][i]
        y = data['top'][i]
        w = data['width'][i]
        h = data['height'][i]
        level = data['level'][i]
        
        print(f"  Text: '{text}'")
        print(f"  Confidence: {conf}%")
        print(f"  Position: ({x}, {y})")
        print(f"  Size: {w}x{h} pixels")
        print(f"  Level: {level} (5=word, 4=line, 3=paragraph)")
        print(f"  Bounding box: ({x}, {y}) to ({x+w}, {y+h})")
        
        # Extract the region to see what's actually in the bounding box
        region = gray[y:y+h, x:x+w]
        print(f"  Region shape: {region.shape}")
        
        # Check if there's a lot of white space below
        # Look at the bottom portion of the detection
        if h > 50:
            bottom_portion = region[int(h*0.6):, :]
            white_pixels = np.sum(bottom_portion > 200)  # Mostly white
            total_bottom = bottom_portion.size
            white_ratio = white_pixels / total_bottom if total_bottom > 0 else 0
            print(f"  Bottom 40% white space ratio: {white_ratio:.2%}")
            
            # Check actual text height (non-white pixels)
            # Find the bottommost non-white pixel
            rows_with_content = np.any(region < 200, axis=1)
            if np.any(rows_with_content):
                actual_text_bottom = np.where(rows_with_content)[0][-1] + 1
                print(f"  Actual text height: {actual_text_bottom}px (detected: {h}px)")
                print(f"  Extra space below text: {h - actual_text_bottom}px")

