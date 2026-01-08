"""Check if contrast enhancement helps detect F2."""
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

# Apply CLAHE contrast enhancement
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
gray_enhanced = clahe.apply(gray)

print("Searching for F2 with contrast enhancement...")

# Try PSM 12 (where F3 was found)
try:
    pil = Image.fromarray(gray_enhanced)
    data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config='--psm 12')
    
    print(f"\nPSM 12 mode with contrast enhancement:")
    f2_found = False
    f3_found = False
    
    for i in range(len(data['text'])):
        text = data['text'][i].strip().upper()
        conf = int(data['conf'][i])
        if conf > 30 and text:
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            
            if 'F2' in text or text == 'F2':
                print(f"  F2 found: '{text}' conf={conf}% at ({x},{y}) size={w}x{h}")
                f2_found = True
            if 'F3' in text or text == 'F3':
                print(f"  F3 found: '{text}' conf={conf}% at ({x},{y}) size={w}x{h}")
                f3_found = True
                # Show nearby detections
                print(f"    Nearby detections:")
                for j in range(len(data['text'])):
                    text2 = data['text'][j].strip()
                    conf2 = int(data['conf'][j])
                    if conf2 > 30 and text2:
                        x2, y2 = data['left'][j], data['top'][j]
                        # Check if within 200 pixels
                        if abs(x2 - x) < 200 and abs(y2 - y) < 200:
                            print(f"      '{text2}' at ({x2},{y2})")
    
    if not f2_found:
        print("  F2 NOT found even with contrast enhancement")
    if not f3_found:
        print("  F3 NOT found")
            
except Exception as e:
    print(f"Error: {e}")

