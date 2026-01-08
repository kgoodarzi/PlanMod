"""
Thin all lines in an image to single-pixel thickness using skeletonization.
This preprocessing step helps with line tracing algorithms.
"""

import cv2
import numpy as np
from pathlib import Path
import argparse


def thin_lines_morphological(image):
    """
    Thin lines using morphological operations (Zhang-Suen thinning algorithm).
    This is a fallback if OpenCV's thinning function is not available.
    
    Args:
        image: Binary image (0 = black line, 255 = white background)
    
    Returns:
        Thinned binary image
    """
    # Ensure binary
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Binarize if needed
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    # Invert: thinning works on white lines on black background
    binary = 255 - binary
    
    # Zhang-Suen thinning algorithm
    thinned = binary.copy()
    prev = np.zeros_like(thinned)
    
    while not np.array_equal(thinned, prev):
        prev = thinned.copy()
        
        # Subiteration 1
        markers = np.zeros_like(thinned)
        for i in range(1, thinned.shape[0] - 1):
            for j in range(1, thinned.shape[1] - 1):
                if thinned[i, j] == 255:
                    p2 = thinned[i-1, j]
                    p3 = thinned[i-1, j+1]
                    p4 = thinned[i, j+1]
                    p5 = thinned[i+1, j+1]
                    p6 = thinned[i+1, j]
                    p7 = thinned[i+1, j-1]
                    p8 = thinned[i, j-1]
                    p9 = thinned[i-1, j-1]
                    
                    B = sum([p2, p3, p4, p5, p6, p7, p8, p9]) // 255
                    A = sum([(p2 == 0 and p3 == 255), (p3 == 0 and p4 == 255),
                            (p4 == 0 and p5 == 255), (p5 == 0 and p6 == 255),
                            (p6 == 0 and p7 == 255), (p7 == 0 and p8 == 255),
                            (p8 == 0 and p9 == 255), (p9 == 0 and p2 == 255)])
                    
                    if (B >= 2 and B <= 6 and A == 1 and
                        p2 * p4 * p6 == 0 and p4 * p6 * p8 == 0):
                        markers[i, j] = 255
        
        thinned = cv2.bitwise_and(thinned, cv2.bitwise_not(markers))
        
        # Subiteration 2
        markers = np.zeros_like(thinned)
        for i in range(1, thinned.shape[0] - 1):
            for j in range(1, thinned.shape[1] - 1):
                if thinned[i, j] == 255:
                    p2 = thinned[i-1, j]
                    p3 = thinned[i-1, j+1]
                    p4 = thinned[i, j+1]
                    p5 = thinned[i+1, j+1]
                    p6 = thinned[i+1, j]
                    p7 = thinned[i+1, j-1]
                    p8 = thinned[i, j-1]
                    p9 = thinned[i-1, j-1]
                    
                    B = sum([p2, p3, p4, p5, p6, p7, p8, p9]) // 255
                    A = sum([(p2 == 0 and p3 == 255), (p3 == 0 and p4 == 255),
                            (p4 == 0 and p5 == 255), (p5 == 0 and p6 == 255),
                            (p6 == 0 and p7 == 255), (p7 == 0 and p8 == 255),
                            (p8 == 0 and p9 == 255), (p9 == 0 and p2 == 255)])
                    
                    if (B >= 2 and B <= 6 and A == 1 and
                        p2 * p4 * p8 == 0 and p2 * p6 * p8 == 0):
                        markers[i, j] = 255
        
        thinned = cv2.bitwise_and(thinned, cv2.bitwise_not(markers))
    
    # Invert back: black lines on white background
    thinned = 255 - thinned
    
    return thinned


def thin_lines_opencv(image):
    """
    Thin lines using OpenCV's thinning function (if available).
    
    Args:
        image: Binary image (0 = black line, 255 = white background)
    
    Returns:
        Thinned binary image, or None if function not available
    """
    try:
        # Check if ximgproc module is available
        import cv2.ximgproc as ximgproc
        
        # Ensure binary
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Binarize if needed
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Invert: thinning works on white lines on black background
        binary = 255 - binary
        
        # Apply thinning
        thinned = ximgproc.thinning(binary, thinningType=ximgproc.THINNING_ZHANGSUEN)
        
        # Invert back: black lines on white background
        thinned = 255 - thinned
        
        return thinned
    except (AttributeError, ImportError):
        return None


def thin_lines_scikit(image):
    """
    Thin lines using scikit-image's skeletonize function.
    
    Args:
        image: Binary image (0 = black line, 255 = white background)
    
    Returns:
        Thinned binary image, or None if scikit-image not available
    """
    try:
        from skimage.morphology import skeletonize
        from skimage import img_as_bool
        
        # Ensure binary
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Binarize if needed
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Invert: skeletonize works on white lines on black background
        binary = 255 - binary
        
        # Convert to boolean (True = white, False = black)
        binary_bool = img_as_bool(binary)
        
        # Skeletonize
        skeleton = skeletonize(binary_bool)
        
        # Convert back to uint8 (255 = white, 0 = black)
        skeleton_uint8 = (skeleton * 255).astype(np.uint8)
        
        # Invert back: black lines on white background
        skeleton_uint8 = 255 - skeleton_uint8
        
        return skeleton_uint8
    except ImportError:
        return None


def thin_lines(image_path, output_path=None, method='auto'):
    """
    Thin all lines in an image to single-pixel thickness.
    
    Args:
        image_path: Path to input image
        output_path: Path to save output (default: input_path with '_thinned' suffix)
        method: 'opencv', 'scikit', 'morphological', or 'auto' (try in order)
    
    Returns:
        Path to output file
    """
    print(f"Loading image: {image_path}")
    image = cv2.imread(str(image_path))
    
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")
    
    print(f"Image size: {image.shape[1]}x{image.shape[0]} pixels")
    
    # Try different methods
    thinned = None
    
    if method == 'auto' or method == 'opencv':
        print("Trying OpenCV thinning...")
        thinned = thin_lines_opencv(image)
        if thinned is not None:
            print("  Successfully used OpenCV thinning")
            method_used = 'opencv'
        elif method == 'opencv':
            raise RuntimeError("OpenCV thinning not available. Install opencv-contrib-python.")
    
    if thinned is None and (method == 'auto' or method == 'scikit'):
        print("Trying scikit-image skeletonize...")
        thinned = thin_lines_scikit(image)
        if thinned is not None:
            print("  Successfully used scikit-image skeletonize")
            method_used = 'scikit'
        elif method == 'scikit':
            raise RuntimeError("scikit-image not available. Install scikit-image.")
    
    if thinned is None and (method == 'auto' or method == 'morphological'):
        print("Using morphological thinning (Zhang-Suen algorithm)...")
        thinned = thin_lines_morphological(image)
        method_used = 'morphological'
        print("  Successfully used morphological thinning")
    
    if thinned is None:
        raise RuntimeError("No thinning method available")
    
    # Determine output path
    if output_path is None:
        input_path = Path(image_path)
        output_path = input_path.parent / f"{input_path.stem}_thinned{input_path.suffix}"
    else:
        output_path = Path(output_path)
    
    # Save output
    cv2.imwrite(str(output_path), thinned)
    print(f"\nSaved thinned image to: {output_path}")
    print(f"Method used: {method_used}")
    
    # Show statistics
    original_binary = cv2.threshold(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image, 
                                    127, 255, cv2.THRESH_BINARY)[1]
    original_line_pixels = np.sum(original_binary < 127)
    thinned_line_pixels = np.sum(thinned < 127)
    
    print(f"Original line pixels: {original_line_pixels}")
    print(f"Thinned line pixels: {thinned_line_pixels}")
    print(f"Reduction: {((original_line_pixels - thinned_line_pixels) / original_line_pixels * 100):.1f}%")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Thin all lines in an image to single-pixel thickness'
    )
    parser.add_argument('input_image', type=str,
                       help='Input image path')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output image path (default: input_path with _thinned suffix)')
    parser.add_argument('--method', type=str, default='auto',
                       choices=['auto', 'opencv', 'scikit', 'morphological'],
                       help='Thinning method (default: auto - tries in order)')
    
    args = parser.parse_args()
    
    thin_lines(args.input_image, args.output, args.method)


if __name__ == '__main__':
    main()

