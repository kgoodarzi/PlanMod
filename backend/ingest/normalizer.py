"""
Image normalization for PlanMod.

Handles orientation correction, resolution normalization,
color space conversion, and preprocessing for downstream analysis.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ImageNormalizer:
    """
    Normalizes images for consistent downstream processing.
    
    Operations:
    - Orientation detection and correction
    - Resolution normalization
    - Color space conversion (grayscale/binary)
    - Noise reduction
    - Border removal
    """
    
    # Target dimensions for normalized output
    DEFAULT_MAX_DIMENSION = 4000  # Max width or height in pixels
    DEFAULT_DPI = 300
    
    def __init__(
        self,
        max_dimension: int = DEFAULT_MAX_DIMENSION,
        target_dpi: int = DEFAULT_DPI,
        convert_grayscale: bool = True,
        apply_denoising: bool = True,
    ):
        """
        Initialize normalizer with configuration.
        
        Args:
            max_dimension: Maximum dimension for output image
            target_dpi: Target DPI for output
            convert_grayscale: Whether to convert to grayscale
            apply_denoising: Whether to apply denoising
        """
        self.max_dimension = max_dimension
        self.target_dpi = target_dpi
        self.convert_grayscale = convert_grayscale
        self.apply_denoising = apply_denoising
    
    def normalize(self, image: np.ndarray) -> np.ndarray:
        """
        Apply full normalization pipeline.
        
        Args:
            image: Input image as numpy array (RGB or grayscale)
            
        Returns:
            Normalized image as numpy array
        """
        logger.info(f"Normalizing image with shape {image.shape}")
        
        # Ensure proper color format
        if len(image.shape) == 2:
            # Already grayscale
            gray = image
            color = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            # RGBA -> RGB
            color = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            gray = cv2.cvtColor(color, cv2.COLOR_RGB2GRAY)
        elif image.shape[2] == 3:
            color = image
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            raise ValueError(f"Unexpected image shape: {image.shape}")
        
        # Detect and correct orientation
        corrected = self._correct_orientation(gray if self.convert_grayscale else color)
        
        # Resize if necessary
        resized = self._resize_image(corrected)
        
        # Remove borders/margins
        cropped = self._remove_borders(resized)
        
        # Apply denoising
        if self.apply_denoising:
            denoised = self._denoise(cropped)
        else:
            denoised = cropped
        
        # Enhance contrast
        enhanced = self._enhance_contrast(denoised)
        
        logger.info(f"Normalization complete. Output shape: {enhanced.shape}")
        
        return enhanced
    
    def _correct_orientation(self, image: np.ndarray) -> np.ndarray:
        """
        Detect and correct image orientation.
        
        Uses edge detection to find dominant angle and rotates if needed.
        
        Args:
            image: Input image
            
        Returns:
            Orientation-corrected image
        """
        # Detect edges
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        
        if lines is None or len(lines) < 10:
            # Not enough lines to determine orientation
            return image
        
        # Calculate dominant angle
        angles = []
        for line in lines[:50]:  # Use first 50 lines
            rho, theta = line[0]
            angle = np.degrees(theta)
            
            # Normalize angle to -45 to 45 range
            if angle > 90:
                angle = angle - 180
            if angle > 45:
                angle = angle - 90
            elif angle < -45:
                angle = angle + 90
            
            angles.append(angle)
        
        # Use median angle (robust to outliers)
        median_angle = np.median(angles)
        
        # Only rotate if angle is significant
        if abs(median_angle) < 0.5:
            return image
        
        logger.info(f"Correcting orientation by {median_angle:.2f} degrees")
        
        # Rotate image
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        
        # Calculate new dimensions
        cos = np.abs(rotation_matrix[0, 0])
        sin = np.abs(rotation_matrix[0, 1])
        new_width = int(height * sin + width * cos)
        new_height = int(height * cos + width * sin)
        
        # Adjust rotation matrix
        rotation_matrix[0, 2] += (new_width - width) / 2
        rotation_matrix[1, 2] += (new_height - height) / 2
        
        # Apply rotation
        rotated = cv2.warpAffine(
            image,
            rotation_matrix,
            (new_width, new_height),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255) if len(image.shape) == 3 else 255,
        )
        
        return rotated
    
    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        """
        Resize image to fit within max dimensions.
        
        Args:
            image: Input image
            
        Returns:
            Resized image
        """
        height, width = image.shape[:2]
        max_dim = max(height, width)
        
        if max_dim <= self.max_dimension:
            return image
        
        scale = self.max_dimension / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        logger.info(f"Resizing from {width}x{height} to {new_width}x{new_height}")
        
        resized = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA,
        )
        
        return resized
    
    def _remove_borders(self, image: np.ndarray) -> np.ndarray:
        """
        Remove empty borders/margins from image.
        
        Args:
            image: Input image
            
        Returns:
            Cropped image
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Find non-white regions
        # Use adaptive threshold to handle varying backgrounds
        _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        
        # Find bounding box of content
        coords = cv2.findNonZero(binary)
        
        if coords is None:
            return image
        
        x, y, w, h = cv2.boundingRect(coords)
        
        # Add small margin
        margin = 20
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(image.shape[1] - x, w + 2 * margin)
        h = min(image.shape[0] - y, h + 2 * margin)
        
        # Crop
        cropped = image[y:y+h, x:x+w]
        
        return cropped
    
    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Apply denoising to image.
        
        Args:
            image: Input image
            
        Returns:
            Denoised image
        """
        if len(image.shape) == 3:
            # Color image
            denoised = cv2.fastNlMeansDenoisingColored(image, None, 3, 3, 7, 21)
        else:
            # Grayscale
            denoised = cv2.fastNlMeansDenoising(image, None, 3, 7, 21)
        
        return denoised
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance image contrast using CLAHE.
        
        Args:
            image: Input image
            
        Returns:
            Contrast-enhanced image
        """
        if len(image.shape) == 3:
            # Convert to LAB color space
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l_channel)
            
            # Merge channels
            lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        else:
            # Grayscale
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)
        
        return enhanced
    
    def to_binary(
        self,
        image: np.ndarray,
        method: str = "adaptive",
    ) -> np.ndarray:
        """
        Convert image to binary (black and white).
        
        Useful for line detection and vectorization.
        
        Args:
            image: Input image (grayscale or color)
            method: Thresholding method ("adaptive", "otsu", "fixed")
            
        Returns:
            Binary image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        if method == "adaptive":
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                2,
            )
        elif method == "otsu":
            _, binary = cv2.threshold(
                gray,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
        else:  # fixed
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        return binary
    
    def detect_drawing_regions(
        self,
        image: np.ndarray,
    ) -> list[Tuple[int, int, int, int]]:
        """
        Detect major drawing regions in image.
        
        Finds rectangular regions that likely contain distinct views.
        
        Args:
            image: Input image
            
        Returns:
            List of bounding boxes (x, y, width, height)
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Apply binary threshold
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Dilate to connect nearby elements
        kernel = np.ones((20, 20), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=3)
        
        # Find contours
        contours, _ = cv2.findContours(
            dilated,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        
        regions = []
        min_area = (image.shape[0] * image.shape[1]) * 0.01  # At least 1% of image
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            if area >= min_area:
                regions.append((x, y, w, h))
        
        # Sort by area (largest first)
        regions.sort(key=lambda r: r[2] * r[3], reverse=True)
        
        return regions


