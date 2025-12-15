"""Client for calling Vision-Language Model APIs."""

import base64
import json
import os
from io import BytesIO
from typing import Dict, List, Optional

import requests
from PIL import Image

from .schema import ComponentAnnotation, VLMResponse, ViewAnnotation


class VLMClient:
    """Client for managed VLM API (Claude, GPT-4 Vision, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize VLM client.
        
        Args:
            api_key: API key (defaults to VLM_API_KEY env var)
            api_endpoint: API endpoint URL (defaults to VLM_API_ENDPOINT env var)
            model: Model name (defaults to VLM_MODEL env var)
        """
        self.api_key = api_key or os.getenv("VLM_API_KEY")
        self.api_endpoint = api_endpoint or os.getenv(
            "VLM_API_ENDPOINT", "https://api.anthropic.com/v1/messages"
        )
        self.model = model or os.getenv("VLM_MODEL", "claude-3-opus-20240229")
        
        if not self.api_key:
            raise ValueError(
                "VLM API key required. Set VLM_API_KEY environment variable or pass api_key."
            )

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buf = BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _create_analysis_prompt(self) -> str:
        """Create prompt for engineering drawing analysis."""
        return """Analyze this balsa model aircraft engineering drawing. The drawing contains front, top, and side orthographic views.

Tasks:
1. Identify and locate the front, top, and side views. Provide bounding boxes (normalized 0-1) for each view.
2. Detect and label components:
   - Spars (main structural beams)
   - Ribs (wing cross-sections)
   - Formers (fuselage cross-sections)
   - Longerons (fuselage stringers)
   - Sticks (rectangular balsa strips)
   - Plates/Sheeting (flat panels)
   - Hardware (hinges, control horns, etc.)
3. For each component, provide:
   - Component type/label
   - Bounding box (normalized coordinates)
   - Any readable dimensions or labels
   - Confidence score (0-1)

Return your analysis as a JSON object with this structure:
{
  "views": [
    {
      "view_type": "front|top|side",
      "bbox": {"x_min": 0.0, "y_min": 0.0, "x_max": 1.0, "y_max": 1.0},
      "confidence": 0.95
    }
  ],
  "components": [
    {
      "label": "spar|rib|longeron|stick|plate|hardware|...",
      "bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.3, "y_max": 0.4},
      "confidence": 0.9,
      "dimensions": "1/8\" x 1/4\"",
      "notes": "Main wing spar"
    }
  ],
  "text_annotations": ["any text labels found in the drawing"]
}

Focus on structural components. Be precise with bounding boxes."""

    def analyze_drawing(
        self, images: Dict[str, Image.Image]
    ) -> Dict[str, VLMResponse]:
        """
        Analyze drawing images using VLM.
        
        Args:
            images: Dictionary mapping view names to PIL Images
        
        Returns:
            Dictionary mapping view names to VLMResponse objects
        """
        results = {}
        
        for view_name, image in images.items():
            try:
                response = self._call_vlm_api(image)
                results[view_name] = response
            except Exception as e:
                # Fallback: create empty response on error
                print(f"Warning: VLM analysis failed for {view_name}: {e}")
                results[view_name] = VLMResponse()
        
        return results

    def _call_vlm_api(self, image: Image.Image) -> VLMResponse:
        """
        Call VLM API with image and prompt.
        
        Supports Claude API format. Can be extended for other providers.
        """
        image_b64 = self._image_to_base64(image)
        prompt = self._create_analysis_prompt()
        
        # Determine API provider from endpoint
        if "anthropic.com" in self.api_endpoint:
            return self._call_claude_api(image_b64, prompt)
        elif "openai.com" in self.api_endpoint:
            return self._call_openai_api(image_b64, prompt)
        else:
            # Generic JSON API format
            return self._call_generic_api(image_b64, prompt)

    def _call_claude_api(self, image_b64: str, prompt: str) -> VLMResponse:
        """Call Claude API (Anthropic)."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        
        response = requests.post(self.api_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result["content"][0]["text"]
        
        return self._parse_response(content)

    def _call_openai_api(self, image_b64: str, prompt: str) -> VLMResponse:
        """Call OpenAI GPT-4 Vision API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 4096,
        }
        
        response = requests.post(self.api_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        return self._parse_response(content)

    def _call_generic_api(self, image_b64: str, prompt: str) -> VLMResponse:
        """Generic API call for custom endpoints."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "image": image_b64,
            "prompt": prompt,
            "model": self.model,
        }
        
        response = requests.post(self.api_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        # Assume response has "content" or "text" field
        content = result.get("content") or result.get("text", "")
        
        return self._parse_response(content)

    def _parse_response(self, content: str) -> VLMResponse:
        """
        Parse VLM response text into structured VLMResponse.
        
        Attempts to extract JSON from the response text.
        """
        # Try to extract JSON from response
        try:
            # Look for JSON code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                # Try to find JSON object directly
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            
            data = json.loads(json_str)
            return VLMResponse(**data, raw_response=content)
        
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback: return empty response with raw text
            print(f"Warning: Failed to parse VLM response: {e}")
            return VLMResponse(raw_response=content)

