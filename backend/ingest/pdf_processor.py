"""
PDF processing for PlanMod.

Handles PDF rasterization and page extraction.
"""

import io
import logging
from typing import List, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Processes PDF files for the ingestion pipeline.
    
    Rasterizes PDF pages to images at configurable DPI.
    """
    
    DEFAULT_DPI = 300
    
    def __init__(self, dpi: int = DEFAULT_DPI):
        """
        Initialize PDF processor.
        
        Args:
            dpi: Resolution for rasterization
        """
        self.dpi = dpi
    
    def rasterize(
        self,
        pdf_data: bytes,
        dpi: Optional[int] = None,
        pages: Optional[List[int]] = None,
    ) -> List[np.ndarray]:
        """
        Rasterize PDF pages to images.
        
        Args:
            pdf_data: PDF file as bytes
            dpi: Optional DPI override
            pages: Optional list of page indices to extract (0-indexed)
            
        Returns:
            List of images as numpy arrays
        """
        dpi = dpi or self.dpi
        
        logger.info(f"Rasterizing PDF at {dpi} DPI")
        
        try:
            # Try PyMuPDF first (faster)
            return self._rasterize_pymupdf(pdf_data, dpi, pages)
        except ImportError:
            logger.warning("PyMuPDF not available, falling back to pdf2image")
            return self._rasterize_pdf2image(pdf_data, dpi, pages)
    
    def _rasterize_pymupdf(
        self,
        pdf_data: bytes,
        dpi: int,
        pages: Optional[List[int]],
    ) -> List[np.ndarray]:
        """
        Rasterize using PyMuPDF (fitz).
        
        Args:
            pdf_data: PDF file as bytes
            dpi: Resolution for rasterization
            pages: Optional list of page indices
            
        Returns:
            List of images as numpy arrays
        """
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        
        images = []
        page_indices = pages if pages else range(len(doc))
        
        for page_idx in page_indices:
            if page_idx >= len(doc):
                logger.warning(f"Page index {page_idx} out of range")
                continue
            
            page = doc[page_idx]
            
            # Calculate zoom factor for target DPI
            zoom = dpi / 72  # PDF default is 72 DPI
            mat = fitz.Matrix(zoom, zoom)
            
            # Render page
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to numpy array
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            img_array = np.array(img)
            
            # Ensure RGB (not RGBA)
            if img_array.shape[-1] == 4:
                img_array = img_array[:, :, :3]
            
            images.append(img_array)
            
            logger.info(f"Rasterized page {page_idx + 1}/{len(doc)}: {img_array.shape}")
        
        doc.close()
        
        return images
    
    def _rasterize_pdf2image(
        self,
        pdf_data: bytes,
        dpi: int,
        pages: Optional[List[int]],
    ) -> List[np.ndarray]:
        """
        Rasterize using pdf2image (requires poppler).
        
        Args:
            pdf_data: PDF file as bytes
            dpi: Resolution for rasterization
            pages: Optional list of page indices
            
        Returns:
            List of images as numpy arrays
        """
        from pdf2image import convert_from_bytes
        
        # pdf2image uses 1-indexed pages
        first_page = None
        last_page = None
        
        if pages:
            first_page = min(pages) + 1
            last_page = max(pages) + 1
        
        pil_images = convert_from_bytes(
            pdf_data,
            dpi=dpi,
            first_page=first_page,
            last_page=last_page,
        )
        
        images = []
        for i, pil_img in enumerate(pil_images):
            img_array = np.array(pil_img)
            
            # Ensure RGB
            if len(img_array.shape) == 2:
                img_array = np.stack([img_array] * 3, axis=-1)
            elif img_array.shape[-1] == 4:
                img_array = img_array[:, :, :3]
            
            images.append(img_array)
            
            logger.info(f"Rasterized page {i + 1}/{len(pil_images)}: {img_array.shape}")
        
        return images
    
    def get_page_count(self, pdf_data: bytes) -> int:
        """
        Get the number of pages in a PDF.
        
        Args:
            pdf_data: PDF file as bytes
            
        Returns:
            Number of pages
        """
        try:
            import fitz
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            count = len(doc)
            doc.close()
            return count
        except ImportError:
            from pdf2image import pdfinfo_from_bytes
            info = pdfinfo_from_bytes(pdf_data)
            return info.get("Pages", 0)
    
    def extract_text(self, pdf_data: bytes, page: int = 0) -> str:
        """
        Extract text from a PDF page.
        
        Args:
            pdf_data: PDF file as bytes
            page: Page index (0-indexed)
            
        Returns:
            Extracted text
        """
        try:
            import fitz
            
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            
            if page >= len(doc):
                return ""
            
            text = doc[page].get_text()
            doc.close()
            
            return text
            
        except ImportError:
            logger.warning("PyMuPDF not available for text extraction")
            return ""
    
    def get_metadata(self, pdf_data: bytes) -> dict:
        """
        Extract metadata from PDF.
        
        Args:
            pdf_data: PDF file as bytes
            
        Returns:
            Metadata dictionary
        """
        try:
            import fitz
            
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            metadata = doc.metadata
            doc.close()
            
            return metadata or {}
            
        except ImportError:
            logger.warning("PyMuPDF not available for metadata extraction")
            return {}


