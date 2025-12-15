"""Tests for VLM client."""

import json
from unittest.mock import Mock, patch

import pytest

from src.vlm_client.client import VLMClient
from src.vlm_client.schema import ComponentAnnotation, VLMResponse, ViewAnnotation


def test_vlm_response_parsing():
    """Test parsing VLM response into structured format."""
    response_text = """
    {
      "views": [
        {
          "view_type": "front",
          "bbox": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 1.0},
          "confidence": 0.95
        }
      ],
      "components": [
        {
          "label": "spar",
          "bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.3, "y_max": 0.4},
          "confidence": 0.9,
          "dimensions": "1/8\" x 1/4\"",
          "notes": "Main wing spar"
        }
      ],
      "text_annotations": ["WING PLANFORM"]
    }
    """
    
    client = VLMClient.__new__(VLMClient)  # Skip __init__ for testing
    response = client._parse_response(response_text)
    
    assert len(response.views) == 1
    assert response.views[0].view_type == "front"
    assert len(response.components) == 1
    assert response.components[0].label == "spar"
    assert response.components[0].confidence == 0.9


def test_vlm_response_with_code_block():
    """Test parsing response with JSON code block."""
    response_text = """
    Here is the analysis:
    ```json
    {
      "views": [{"view_type": "top", "bbox": {"x_min": 0, "y_min": 0, "x_max": 1, "y_max": 1}, "confidence": 0.9}],
      "components": []
    }
    ```
    """
    
    client = VLMClient.__new__(VLMClient)
    response = client._parse_response(response_text)
    
    assert len(response.views) == 1
    assert response.views[0].view_type == "top"


def test_vlm_response_fallback():
    """Test fallback when JSON parsing fails."""
    response_text = "This is not valid JSON"
    
    client = VLMClient.__new__(VLMClient)
    response = client._parse_response(response_text)
    
    assert response.raw_response == response_text
    assert len(response.views) == 0
    assert len(response.components) == 0

