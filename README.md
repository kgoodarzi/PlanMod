# Image Cleanup - Remove Text and Leaders from Technical Diagrams

This tool programmatically removes text labels and leader lines (arrows/pointers) from technical diagrams and blueprints while preserving structural elements.

## Features

- **Text Detection**: Uses morphological operations or OCR to detect text regions
- **Leader Detection**: Identifies short line segments and small features that are likely arrows/pointers
- **Smart Removal**: Uses inpainting to seamlessly fill removed regions, preserving underlying structure
- **Configurable**: Adjustable parameters for different image types

## Installation

```bash
pip install -r requirements.txt
```

For OCR-based text detection (optional, more accurate but slower):
- On Linux: `sudo apt-get install tesseract-ocr`
- On macOS: `brew install tesseract`
- On Windows: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

## Usage

### Command Line

```bash
python remove_text_leaders.py input_image.png -o output_image.png
```

Options:
- `-o, --output`: Output path (default: adds `_cleaned` suffix)
- `-m, --method`: Text detection method (`morphology` or `ocr`, default: `morphology`)
- `--no-inpaint`: Disable inpainting (use white fill instead)
- `-d, --dilation`: Dilation size for mask expansion (default: 3)

### Python API

```python
from remove_text_leaders import remove_text_and_leaders

# Basic usage
result = remove_text_and_leaders('diagram.png')

# With options
result = remove_text_and_leaders(
    'diagram.png',
    output_path='cleaned.png',
    method='morphology',
    use_inpainting=True,
    dilation_size=3
)
```

## How It Works

1. **Text Detection**: 
   - Morphology method: Uses morphological operations to detect rectangular text-like patterns
   - OCR method: Uses Tesseract OCR to identify text regions (more accurate but requires installation)

2. **Leader Detection**: 
   - Detects short line segments using Hough line transform
   - Identifies small isolated features that may be arrowheads

3. **Removal**: 
   - Combines text and leader masks
   - Uses OpenCV's inpainting algorithm to fill removed regions while preserving structure
   - Alternatively, can simply fill with white

## Tuning Parameters

For different image types, you may need to adjust:

- **Text detection thresholds** (in `detect_text_regions`):
  - `aspect_ratio` range: Adjust for text orientation
  - `area` threshold: Adjust for text size

- **Leader detection thresholds** (in `detect_leaders`):
  - `minLineLength`/`maxLineGap`: Adjust for leader line characteristics
  - `length` range: Adjust for typical leader lengths

- **Dilation size**: Increase if text/leaders aren't fully removed, decrease if too much is removed

## Examples

```bash
# Basic usage
python remove_text_leaders.py blueprint.png

# Use OCR for better text detection
python remove_text_leaders.py blueprint.png -m ocr

# Disable inpainting (faster, but leaves white regions)
python remove_text_leaders.py blueprint.png --no-inpaint

# Increase dilation for more aggressive removal
python remove_text_leaders.py blueprint.png -d 5
```

