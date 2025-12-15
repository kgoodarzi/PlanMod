"""
OCR module for PlanMod.

Extracts text from drawings using Amazon Textract and local OCR.
"""

from backend.ocr.handler import OCRHandler
from backend.ocr.textract_client import TextractClient
from backend.ocr.text_processor import TextProcessor

__all__ = [
    "OCRHandler",
    "TextractClient",
    "TextProcessor",
]


