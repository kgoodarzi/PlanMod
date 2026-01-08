"""Analyze OCR detections to understand text characteristics."""
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
pil = Image.fromarray(gray)

data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config='--psm 11')

print("All OCR detections:")
for i in range(len(data['text'])):
    text = data['text'][i].strip()
    conf = int(data['conf'][i])
    if conf > 30 and text:
        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
        aspect = w/h if h > 0 else 0
        print(f"  '{text}' conf={conf}% at ({x},{y}) size={w}x{h} aspect={aspect:.2f}")

