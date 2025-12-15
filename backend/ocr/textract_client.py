"""
Amazon Textract client for OCR.
"""

import logging
from typing import Any, Optional

import boto3

from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class TextractClient:
    """
    Client for Amazon Textract OCR service.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        """Initialize Textract client."""
        self.settings = settings or get_settings()
        self._client: Optional[Any] = None
    
    @property
    def client(self) -> Any:
        """Get or create Textract client."""
        if self._client is None:
            config = self.settings.get_boto3_config()
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._client = session.client("textract", **config)
            else:
                self._client = boto3.client("textract", **config)
        
        return self._client
    
    async def detect_text(self, image_bytes: bytes) -> list[dict]:
        """
        Detect text in image using Textract.
        
        Args:
            image_bytes: Image as bytes
            
        Returns:
            List of detected text items
        """
        logger.info("Running Textract text detection")
        
        response = self.client.detect_document_text(
            Document={"Bytes": image_bytes}
        )
        
        texts = []
        
        for block in response.get("Blocks", []):
            if block["BlockType"] in ("LINE", "WORD"):
                bbox = block.get("Geometry", {}).get("BoundingBox", {})
                
                texts.append({
                    "text": block.get("Text", ""),
                    "x": bbox.get("Left", 0),
                    "y": bbox.get("Top", 0),
                    "width": bbox.get("Width", 0),
                    "height": bbox.get("Height", 0),
                    "confidence": block.get("Confidence", 0) / 100,
                    "block_type": block["BlockType"],
                })
        
        return texts
    
    async def analyze_document(
        self,
        image_bytes: bytes,
        features: Optional[list[str]] = None,
    ) -> dict:
        """
        Analyze document with Textract.
        
        Args:
            image_bytes: Image as bytes
            features: Features to analyze (TABLES, FORMS)
            
        Returns:
            Analysis results
        """
        features = features or self.settings.ai.textract.features
        
        response = self.client.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=features,
        )
        
        return {
            "blocks": response.get("Blocks", []),
            "document_metadata": response.get("DocumentMetadata", {}),
        }


