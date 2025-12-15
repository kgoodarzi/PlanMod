"""
Amazon Bedrock Claude VLM client.

Implements VLM client using Claude on Amazon Bedrock.
"""

import json
import logging
from typing import Any, Optional

import boto3

from backend.shared.config import get_settings
from backend.vlm_client.base import (
    VLMClient,
    VLMResponse,
    Region,
    ComponentClassification,
)
from backend.vlm_client.prompts import (
    SEGMENT_REGIONS_PROMPT,
    CLASSIFY_COMPONENT_PROMPT,
    EXTRACT_ANNOTATIONS_PROMPT,
    DESCRIBE_DRAWING_PROMPT,
)

logger = logging.getLogger(__name__)


class BedrockClaudeVLM(VLMClient):
    """
    VLM client using Claude on Amazon Bedrock.
    
    Supports Claude 3 and later models with vision capabilities.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize Bedrock Claude client.
        
        Args:
            settings: Optional settings override
        """
        self.settings = settings or get_settings()
        self._client: Optional[Any] = None
    
    @property
    def client(self) -> Any:
        """Get or create Bedrock runtime client."""
        if self._client is None:
            from botocore.config import Config as BotoConfig
            
            # Increase timeout for large models like Claude Opus
            boto_config = BotoConfig(
                read_timeout=300,  # 5 minutes
                connect_timeout=60,
                retries={'max_attempts': 2}
            )
            
            config = self.settings.get_boto3_config()
            config["region_name"] = self.settings.ai.bedrock.region
            config["config"] = boto_config
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._client = session.client("bedrock-runtime", **config)
            else:
                self._client = boto3.client("bedrock-runtime", **config)
        
        return self._client
    
    @property
    def model_id(self) -> str:
        """Get the configured VLM model ID."""
        return self.settings.ai.bedrock.vlm_model_id
    
    async def analyze_image(
        self,
        image: bytes,
        prompt: str,
        response_schema: Optional[dict] = None,
    ) -> VLMResponse:
        """
        Analyze an image with a text prompt.
        
        Args:
            image: Image data as bytes
            prompt: Text prompt
            response_schema: Optional JSON schema for output
            
        Returns:
            VLMResponse with results
        """
        logger.info(f"Analyzing image with prompt: {prompt[:100]}...")
        
        try:
            base64_data, media_type = self._encode_image(image)
            
            # Build message
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ]
            
            # Add schema instruction if provided
            system_prompt = "You are an expert at analyzing technical drawings and CAD documents."
            if response_schema:
                system_prompt += f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}"
            
            # Call Bedrock
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.settings.ai.bedrock.max_tokens,
                    "temperature": self.settings.ai.bedrock.temperature,
                    "system": system_prompt,
                    "messages": messages,
                }),
            )
            
            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [])
            
            if not content:
                return VLMResponse(
                    success=False,
                    raw_response="",
                    error="Empty response from model",
                    model_id=self.model_id,
                )
            
            raw_text = content[0].get("text", "")
            
            # Try to parse as JSON if schema was provided
            structured_data = None
            if response_schema:
                try:
                    # Extract JSON from response
                    structured_data = self._extract_json(raw_text)
                except Exception as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
            
            return VLMResponse(
                success=True,
                raw_response=raw_text,
                structured_data=structured_data,
                tokens_used=response_body.get("usage", {}).get("output_tokens", 0),
                model_id=self.model_id,
            )
            
        except Exception as e:
            logger.error(f"VLM analysis failed: {e}")
            return VLMResponse(
                success=False,
                raw_response="",
                error=str(e),
                model_id=self.model_id,
            )
    
    async def segment_regions(
        self,
        image: bytes,
        region_types: Optional[list[str]] = None,
    ) -> VLMResponse:
        """
        Segment a drawing into distinct regions.
        
        Args:
            image: Image data as bytes
            region_types: Optional expected region types
            
        Returns:
            VLMResponse with detected regions
        """
        prompt = SEGMENT_REGIONS_PROMPT
        if region_types:
            prompt += f"\n\nExpected region types: {', '.join(region_types)}"
        
        schema = {
            "type": "object",
            "properties": {
                "regions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "type": {"type": "string"},
                            "x_percent": {"type": "number"},
                            "y_percent": {"type": "number"},
                            "width_percent": {"type": "number"},
                            "height_percent": {"type": "number"},
                            "confidence": {"type": "number"},
                            "description": {"type": "string"},
                        },
                    },
                },
            },
        }
        
        response = await self.analyze_image(image, prompt, schema)
        
        if response.success and response.structured_data:
            regions = []
            for r in response.structured_data.get("regions", []):
                regions.append(Region(
                    x=r.get("x_percent", 0) / 100,
                    y=r.get("y_percent", 0) / 100,
                    width=r.get("width_percent", 0) / 100,
                    height=r.get("height_percent", 0) / 100,
                    label=r.get("label", "unknown"),
                    confidence=r.get("confidence", 0.5),
                    description=r.get("description", ""),
                    attributes={"type": r.get("type", "unknown")},
                ))
            response.regions = regions
        
        return response
    
    async def classify_component(
        self,
        image_crop: bytes,
        context: str,
        component_types: Optional[list[str]] = None,
    ) -> VLMResponse:
        """
        Classify a component from an image crop.
        
        Args:
            image_crop: Cropped image of component
            context: Contextual information
            component_types: Possible component types
            
        Returns:
            VLMResponse with classification
        """
        prompt = CLASSIFY_COMPONENT_PROMPT.format(context=context)
        
        if component_types:
            prompt += f"\n\nPossible component types: {', '.join(component_types)}"
        
        schema = {
            "type": "object",
            "properties": {
                "component_type": {"type": "string"},
                "confidence": {"type": "number"},
                "description": {"type": "string"},
                "suggested_name": {"type": "string"},
                "material": {"type": "string"},
                "dimensions": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "string"},
                        "height": {"type": "string"},
                        "thickness": {"type": "string"},
                    },
                },
                "alternatives": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
        
        response = await self.analyze_image(image_crop, prompt, schema)
        
        if response.success and response.structured_data:
            data = response.structured_data
            response.components = [ComponentClassification(
                component_type=data.get("component_type", "unknown"),
                confidence=data.get("confidence", 0.5),
                description=data.get("description", ""),
                suggested_name=data.get("suggested_name", ""),
                material=data.get("material"),
                dimensions=data.get("dimensions"),
                alternatives=data.get("alternatives", []),
            )]
        
        return response
    
    async def extract_annotations(
        self,
        image: bytes,
    ) -> VLMResponse:
        """
        Extract text annotations from a drawing.
        
        Args:
            image: Image data as bytes
            
        Returns:
            VLMResponse with annotations
        """
        schema = {
            "type": "object",
            "properties": {
                "annotations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "type": {"type": "string"},  # dimension, label, note
                            "x_percent": {"type": "number"},
                            "y_percent": {"type": "number"},
                            "value": {"type": "number"},
                            "unit": {"type": "string"},
                        },
                    },
                },
            },
        }
        
        return await self.analyze_image(image, EXTRACT_ANNOTATIONS_PROMPT, schema)
    
    async def describe_drawing(
        self,
        image: bytes,
    ) -> VLMResponse:
        """
        Generate a high-level description of a drawing.
        
        Args:
            image: Image data as bytes
            
        Returns:
            VLMResponse with description
        """
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "drawing_type": {"type": "string"},
                "subject": {"type": "string"},
                "views_identified": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "main_components": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "scale": {"type": "string"},
                "notes": {"type": "string"},
            },
        }
        
        return await self.analyze_image(image, DESCRIBE_DRAWING_PROMPT, schema)
    
    async def analyze_with_prompt(
        self,
        image: bytes,
        prompt: str,
    ) -> VLMResponse:
        """
        Analyze an image with a custom prompt, expecting JSON array response.
        
        Args:
            image: Image data as bytes
            prompt: Custom analysis prompt
            
        Returns:
            VLMResponse with structured data
        """
        logger.info(f"Analyzing image with custom prompt...")
        
        try:
            base64_data, media_type = self._encode_image(image)
            
            # Build message with stronger JSON instruction
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ]
            
            system_prompt = """You are an expert at analyzing technical drawings, CAD documents, and model aircraft plans. 
            
When asked to identify components, be thorough and extract ALL visible labeled parts.
Always respond with valid JSON. Do not include any text before or after the JSON.
If the prompt asks for a JSON array, respond with just the array starting with [ and ending with ]."""

            # Call Bedrock
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.settings.ai.bedrock.max_tokens,
                    "temperature": 0.2,  # Lower temperature for more consistent output
                    "system": system_prompt,
                    "messages": messages,
                }),
            )
            
            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [])
            
            if not content:
                return VLMResponse(
                    success=False,
                    raw_response="",
                    error="Empty response from model",
                    model_id=self.model_id,
                )
            
            raw_text = content[0].get("text", "")
            
            # Try to parse as JSON
            structured_data = None
            try:
                structured_data = self._extract_json_array(raw_text)
            except Exception as e:
                logger.warning(f"Failed to parse JSON array: {e}")
                # Try as object
                try:
                    structured_data = self._extract_json(raw_text)
                except Exception:
                    pass
            
            return VLMResponse(
                success=True,
                raw_response=raw_text,
                structured_data=structured_data,
                tokens_used=response_body.get("usage", {}).get("output_tokens", 0),
                model_id=self.model_id,
            )
            
        except Exception as e:
            logger.error(f"VLM analysis with prompt failed: {e}")
            return VLMResponse(
                success=False,
                raw_response="",
                error=str(e),
                model_id=self.model_id,
            )
    
    def _extract_json_array(self, text: str) -> list:
        """
        Extract JSON array from text response.
        
        Args:
            text: Response text
            
        Returns:
            Parsed JSON list
        """
        import re
        
        # Try direct parse first
        text = text.strip()
        if text.startswith('['):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        
        # Look for ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Look for [ ... ] anywhere in text
        bracket_match = re.search(r"\[[\s\S]*\]", text)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Could not extract JSON array from response")
    
    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from text response.
        
        Handles cases where JSON is wrapped in markdown code blocks.
        
        Args:
            text: Response text
            
        Returns:
            Parsed JSON dict
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract from code blocks
        import re
        
        # Look for ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Look for { ... } anywhere in text
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Could not extract JSON from response: {text[:200]}...")

