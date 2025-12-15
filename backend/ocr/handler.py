"""
Main handler for OCR module.
"""

import logging
from typing import Any, Optional

import numpy as np

from backend.shared.config import get_settings
from backend.shared.models import Annotation, BoundingBox
from backend.ocr.textract_client import TextractClient
from backend.ocr.text_processor import TextProcessor

logger = logging.getLogger(__name__)


class OCRHandler:
    """
    Main OCR handler combining Textract and local processing.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        """Initialize OCR handler."""
        self.settings = settings or get_settings()
        self.textract_client = TextractClient(settings)
        self.text_processor = TextProcessor()
    
    async def extract_text(
        self,
        image: np.ndarray,
        use_textract: bool = True,
    ) -> list[Annotation]:
        """
        Extract all text from image.
        
        Args:
            image: Input image
            use_textract: Whether to use Textract (vs local OCR)
            
        Returns:
            List of text annotations
        """
        logger.info("Extracting text from image")
        
        # Convert image to bytes
        from PIL import Image
        import io
        
        pil_image = Image.fromarray(image)
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        
        if use_textract:
            try:
                raw_texts = await self.textract_client.detect_text(image_bytes)
            except Exception as e:
                logger.warning(f"Textract failed, falling back to local OCR: {e}")
                raw_texts = self._local_ocr(image)
        else:
            raw_texts = self._local_ocr(image)
        
        # Process and classify texts
        annotations = []
        
        for text_item in raw_texts:
            annotation = self.text_processor.process_text(
                text_item["text"],
                BoundingBox(
                    x=text_item.get("x", 0),
                    y=text_item.get("y", 0),
                    width=text_item.get("width", 100),
                    height=text_item.get("height", 20),
                ),
                text_item.get("confidence", 1.0),
            )
            annotations.append(annotation)
        
        logger.info(f"Extracted {len(annotations)} text annotations")
        
        return annotations
    
    def _local_ocr(self, image: np.ndarray) -> list[dict]:
        """Run local OCR using pytesseract."""
        try:
            import pytesseract
            
            # Run OCR
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
            )
            
            texts = []
            n_boxes = len(data["text"])
            
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = int(data["conf"][i])
                
                if text and conf > 30:  # Filter low confidence
                    texts.append({
                        "text": text,
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                        "confidence": conf / 100,
                    })
            
            return texts
            
        except Exception as e:
            logger.error(f"Local OCR failed: {e}")
            return []


