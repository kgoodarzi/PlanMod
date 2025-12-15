"""
Base VLM client interface.

Defines the abstract interface for vision-language model clients.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Region:
    """A detected region in an image."""
    
    x: float
    y: float
    width: float
    height: float
    label: str
    confidence: float = 1.0
    description: str = ""
    attributes: dict = field(default_factory=dict)


@dataclass
class ComponentClassification:
    """Classification result for a component."""
    
    component_type: str
    confidence: float
    description: str
    suggested_name: str = ""
    material: Optional[str] = None
    dimensions: Optional[dict] = None
    alternatives: list[str] = field(default_factory=list)


@dataclass
class VLMResponse:
    """Response from VLM analysis."""
    
    success: bool
    raw_response: str
    structured_data: Optional[dict] = None
    regions: list[Region] = field(default_factory=list)
    components: list[ComponentClassification] = field(default_factory=list)
    error: Optional[str] = None
    tokens_used: int = 0
    model_id: str = ""


class VLMClient(ABC):
    """
    Abstract base class for Vision-Language Model clients.
    
    Implementations should provide access to a VLM capable of:
    - Analyzing technical drawings
    - Segmenting regions
    - Classifying components
    - Extracting structured information
    """
    
    @abstractmethod
    async def analyze_image(
        self,
        image: bytes,
        prompt: str,
        response_schema: Optional[dict] = None,
    ) -> VLMResponse:
        """
        Analyze an image with a text prompt.
        
        Args:
            image: Image data as bytes (PNG or JPEG)
            prompt: Text prompt describing what to analyze
            response_schema: Optional JSON schema for structured output
            
        Returns:
            VLMResponse with analysis results
        """
        pass
    
    @abstractmethod
    async def segment_regions(
        self,
        image: bytes,
        region_types: Optional[list[str]] = None,
    ) -> VLMResponse:
        """
        Segment a drawing into distinct regions.
        
        Args:
            image: Image data as bytes
            region_types: Optional list of expected region types
                (e.g., ["top_view", "side_view", "detail"])
            
        Returns:
            VLMResponse with detected regions
        """
        pass
    
    @abstractmethod
    async def classify_component(
        self,
        image_crop: bytes,
        context: str,
        component_types: Optional[list[str]] = None,
    ) -> VLMResponse:
        """
        Classify a component from an image crop.
        
        Args:
            image_crop: Cropped image of the component
            context: Contextual information about the component
            component_types: Optional list of possible component types
            
        Returns:
            VLMResponse with classification results
        """
        pass
    
    @abstractmethod
    async def extract_annotations(
        self,
        image: bytes,
    ) -> VLMResponse:
        """
        Extract text annotations and labels from a drawing.
        
        Args:
            image: Image data as bytes
            
        Returns:
            VLMResponse with extracted annotations
        """
        pass
    
    @abstractmethod
    async def describe_drawing(
        self,
        image: bytes,
    ) -> VLMResponse:
        """
        Generate a high-level description of a drawing.
        
        Args:
            image: Image data as bytes
            
        Returns:
            VLMResponse with drawing description
        """
        pass
    
    def _encode_image(self, image: bytes) -> tuple[str, str]:
        """
        Encode image to base64 and detect media type.
        
        Args:
            image: Image data as bytes
            
        Returns:
            Tuple of (base64_data, media_type)
        """
        import base64
        
        # Detect media type from magic bytes
        if image[:8] == b"\x89PNG\r\n\x1a\n":
            media_type = "image/png"
        elif image[:2] == b"\xff\xd8":
            media_type = "image/jpeg"
        elif image[:4] == b"GIF8":
            media_type = "image/gif"
        elif image[:4] == b"RIFF" and image[8:12] == b"WEBP":
            media_type = "image/webp"
        else:
            # Default to PNG
            media_type = "image/png"
        
        base64_data = base64.b64encode(image).decode("utf-8")
        
        return base64_data, media_type


