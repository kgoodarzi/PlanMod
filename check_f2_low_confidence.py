"""Check for F2 at any confidence level."""
import cv2
from PIL import Image
import pytesseract
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

img = cv2.imread('IMG_9236.JPEG')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Try with contrast enhancement
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
gray_enhanced = clahe.apply(gray)

print("Searching for F2 at ANY confidence level...")
print("=" * 60)

# Try all PSM modes
for psm in [11, 6, 12, 8, 7, 13]:
    try:
        for enhanced in [False, True]:
            test_gray = gray_enhanced if enhanced else gray
            pil = Image.fromarray(test_gray)
            data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config=f'--psm {psm}')
            
            f2_detections = []
            f3_detections = []
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip().upper()
                conf = int(data['conf'][i])
                if conf > -1:  # Any confidence, even negative
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    
                    # Check for F2 in any form
                    if 'F2' in text or text == 'F2' or 'F' in text and '2' in text:
                        f2_detections.append((text, conf, x, y, w, h))
                    if 'F3' in text or text == 'F3':
                        f3_detections.append((text, conf, x, y, w, h))
            
            if f2_detections or f3_detections:
                mode_name = "enhanced" if enhanced else "original"
                print(f"\nPSM {psm} ({mode_name}):")
                if f2_detections:
                    print("  F2 found:")
                    for det in f2_detections:
                        print(f"    '{det[0]}' conf={det[1]}% at ({det[2]},{det[3]}) size={det[4]}x{det[5]}")
                else:
                    print("  F2 NOT found")
                if f3_detections:
                    print("  F3 found:")
                    for det in f3_detections:
                        print(f"    '{det[0]}' conf={det[1]}% at ({det[2]},{det[3]}) size={det[4]}x{det[5]}")
    except Exception as e:
        print(f"PSM {psm} failed: {e}")

# Also check near F3 location (1027, 389)
print("\n" + "=" * 60)
print("Checking region near F3 (1027, 389):")
f3_x, f3_y = 1027, 389
region = gray[f3_y-100:f3_y+100, f3_x-200:f3_x+200]
if region.size > 0:
    pil_region = Image.fromarray(region)
    data_region = pytesseract.image_to_data(pil_region, output_type=pytesseract.Output.DICT, config='--psm 8')
    print("  Detections in region:")
    for i in range(len(data_region['text'])):
        text = data_region['text'][i].strip()
        conf = int(data_region['conf'][i])
        if conf > -1 and text:
            x, y = data_region['left'][i], data_region['top'][i]
            print(f"    '{text}' conf={conf}% at ({x},{y})")

