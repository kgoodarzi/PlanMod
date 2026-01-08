# Improvements Made to Text/Leader Removal

## Analysis Results

Comparing automated cleaning vs manual cleaning:
- **Manual removed**: 58,116 pixels
- **Current auto removes**: ~84,000-91,000 pixels (varies by version)
- **Missed items**: ~38,000-41,000 pixels (text/leaders that should be removed but aren't)
- **Over-removed**: ~61,000-74,000 pixels (structural elements that shouldn't be removed)

## Key Improvements Implemented

### 1. Enhanced Text Detection
- **Adaptive thresholding**: Better handles varying contrast
- **Multiple kernel sizes**: Catches different text sizes
- **Connected component analysis**: Finds isolated text characters
- **Increased size limits**: Now detects text up to 3000 pixels (was 1500)
- **More lenient aspect ratios**: Handles wider text blocks

### 2. Improved Leader Detection
- **More conservative length limits**: Only very short lines (8% of diagonal, was 15%)
- **Smaller feature detection**: Only very small isolated features (<150 pixels, was 300)
- **Better filtering**: Avoids removing structural elements

### 3. Structural Element Preservation
- **Length-based filtering**: Preserves lines longer than 12% of diagonal
- **Area-based filtering**: Preserves features larger than 1.5% of image
- **Dimension-based filtering**: Preserves features spanning >30% of width/height
- **Thickness-based filtering**: Preserves thick lines (>8 pixels wide)

### 4. Refined Mask Application
- **Reduced dilation**: Less aggressive expansion (1 iteration instead of 2)
- **Better inpainting**: Uses INPAINT_TELEA with radius 5

## Remaining Challenges

### Missed Text Characteristics
- Average area: ~670-740 pixels
- Average width: ~46-50 pixels
- Average height: ~61-64 pixels
- Average aspect ratio: ~0.80 (slightly wider than tall)

These are medium-sized text blocks that may be:
- Connected to structural elements
- In areas with complex backgrounds
- Partially obscured or low contrast

### Over-Removed Items
- Average area: ~200-350 pixels
- Some larger regions up to 5,600 pixels

These might be:
- Small structural details
- Thin structural lines
- Features near text that get caught in dilation

## Recommendations for Further Improvement

1. **Use OCR-based detection** (if pytesseract is available):
   ```bash
   python remove_text_leaders.py IMG_9236.JPEG -m ocr
   ```

2. **Adjust parameters** for your specific image type:
   - Increase `-d` (dilation) if text isn't fully removed
   - Decrease `-d` if too much is being removed
   - Try `--no-inpaint` if inpainting creates artifacts

3. **Two-pass approach**: 
   - First pass: Remove obvious text/leaders
   - Second pass: Fine-tune based on results

4. **Machine learning approach**: Train a model to classify text vs structure (more complex but potentially more accurate)

## Current Best Version

The `IMG_9236_final.JPEG` version shows the best balance, but you may want to:
- Manually review and adjust parameters
- Use the visualization tools to see what's being detected
- Consider a hybrid approach (automated + manual touch-up)

