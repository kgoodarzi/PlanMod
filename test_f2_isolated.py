"""Test OCR detection on isolated F2 image."""
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

# Read the isolated F2 image
img = cv2.imread('F2.jpg')
if img is None:
    print("Error: Could not read F2.jpg")
    exit(1)

print(f"F2.jpg image size: {img.shape[1]}x{img.shape[0]} pixels")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Try with contrast enhancement
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
gray_enhanced = clahe.apply(gray)

print("\n" + "=" * 60)
print("Testing OCR on isolated F2 image")
print("=" * 60)

# Try all PSM modes
for psm in [11, 6, 12, 8, 7, 13, 10]:
    for enhanced in [False, True]:
        test_gray = gray_enhanced if enhanced else gray
        pil = Image.fromarray(test_gray)
        
        try:
            data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config=f'--psm {psm}')
            
            detections = []
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                conf = int(data['conf'][i])
                if conf > -1 and text:  # Any confidence
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    detections.append((text, conf, x, y, w, h))
            
            if detections:
                mode_name = "enhanced" if enhanced else "original"
                print(f"\nPSM {psm} ({mode_name}):")
                for det in detections:
                    text, conf, x, y, w, h = det
                    # Check if it's F2 or contains F2
                    is_f2 = 'F2' in text.upper() or (text.upper() == 'F' and len(detections) > 1)
                    marker = " *** F2 DETECTED! ***" if is_f2 else ""
                    print(f"  '{text}' conf={conf}% at ({x},{y}) size={w}x{h}{marker}")
        except Exception as e:
            print(f"PSM {psm} failed: {e}")

# Also try with different preprocessing
print("\n" + "=" * 60)
print("Trying additional preprocessing methods:")
print("=" * 60)

# Method 1: Threshold
_, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
pil_thresh = Image.fromarray(thresh)
data_thresh = pytesseract.image_to_data(pil_thresh, output_type=pytesseract.Output.DICT, config='--psm 8')
print("\nThreshold preprocessing:")
for i in range(len(data_thresh['text'])):
    text = data_thresh['text'][i].strip()
    conf = int(data_thresh['conf'][i])
    if conf > -1 and text:
        print(f"  '{text}' conf={conf}%")

# Method 2: Adaptive threshold
adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
pil_adaptive = Image.fromarray(adaptive)
data_adaptive = pytesseract.image_to_data(pil_adaptive, output_type=pytesseract.Output.DICT, config='--psm 8')
print("\nAdaptive threshold preprocessing:")
for i in range(len(data_adaptive['text'])):
    text = data_adaptive['text'][i].strip()
    conf = int(data_adaptive['conf'][i])
    if conf > -1 and text:
        print(f"  '{text}' conf={conf}%")

