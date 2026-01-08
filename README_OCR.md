# OCR-Based Text Removal

Simple, focused script to remove text from technical diagrams using OCR (Tesseract).

## Quick Start

```bash
# Basic usage
python remove_text_ocr.py IMG_9236.JPEG

# With custom output
python remove_text_ocr.py IMG_9236.JPEG -o output.JPEG

# Compare with reference
python remove_text_ocr.py IMG_9236.JPEG -o output.JPEG --compare IMG_9236_No_Text.jpg

# Adjust parameters
python remove_text_ocr.py IMG_9236.JPEG -p 2 -d 1  # padding=2, dilation=1
```

## Features

- **OCR-based detection**: Uses Tesseract OCR with multiple PSM modes (11, 6, 12) for comprehensive text detection
- **Automatic Tesseract detection**: Finds Tesseract installation on Windows automatically
- **Duplicate removal**: Merges overlapping detections from different PSM modes
- **Smart padding**: Adjusts padding based on text size
- **Inpainting**: Uses OpenCV's inpainting to seamlessly fill removed regions

## Results

On `IMG_9236.JPEG`:
- Detects ~28-30 text regions
- Removes ~24% of image (text regions)
- **~4% difference from reference** (`IMG_9236_No_Text.jpg`)

## Visualization

```bash
# Visualize what text is being detected
python visualize_text_detection.py IMG_9236.JPEG
```

## Parameters

- `-p, --padding`: Padding around detected text (default: auto, 2px)
- `-d, --dilation`: Dilation iterations to expand mask (default: 1, use 0 for no dilation)
- `--tight`: Use minimal 1px padding to preserve nearby elements
- `--fixed-padding N`: Use fixed padding for all text (most consistent mask sizes)
- `--enhance-contrast`: Apply CLAHE contrast enhancement before OCR (may help detect difficult text)
- `-o, --output`: Output file path
- `--compare`: Path to reference image for comparison

## Requirements

- Python 3.7+
- opencv-python
- numpy
- Pillow
- pytesseract
- Tesseract OCR (install from https://github.com/UB-Mannheim/tesseract/wiki on Windows)

## How It Works

1. **Preprocessing** (optional): Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) if `--enhance-contrast` is used. This improves OCR detection on low-contrast images.

2. **Text Detection**: Uses Tesseract OCR with multiple PSM (Page Segmentation Mode) settings:
   - PSM 11: Sparse text (best for scattered labels)
   - PSM 6: Single uniform block
   - PSM 12: Sparse text with orientation detection

3. **Filtering**: Removes false positives based on text characteristics (aspect ratio, confidence, size, character content)

4. **Duplicate Removal**: Merges overlapping detections, keeping the highest confidence ones

5. **Mask Creation**: Creates a binary mask of all text regions with consistent or adaptive padding

6. **Inpainting**: Uses OpenCV's INPAINT_TELEA algorithm to fill removed regions

## Tips

- **Consistent mask sizes**: Use `--fixed-padding 2` to ensure all text masks are the same size
- **Preserve nearby elements**: Use `--tight -d 0` for minimal padding and no dilation
- **Difficult text detection**: Try `--enhance-contrast` to improve OCR on low-contrast images
- **If text is missed**: Try `--enhance-contrast` or increase padding (`-p 4` or `-p 5`)
- **If too much is removed**: Decrease padding (`-p 1` or `-p 2`) or use `-d 0` to disable dilation
- **For better accuracy**: Ensure image has good contrast (text should be clearly visible)

## Example Commands

```bash
# Recommended: Consistent masks with contrast enhancement
python remove_text_ocr.py image.JPEG -o output.JPEG --fixed-padding 2 --enhance-contrast

# Minimal masks to preserve leader lines
python remove_text_ocr.py image.JPEG -o output.JPEG --tight -d 0

# Custom padding with contrast enhancement
python remove_text_ocr.py image.JPEG -o output.JPEG -p 1 --enhance-contrast -d 0
```

