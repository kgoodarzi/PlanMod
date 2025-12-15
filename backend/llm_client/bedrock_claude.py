"""
Amazon Bedrock Claude LLM client.

Implements LLM client using Claude on Amazon Bedrock.
"""

import json
import logging
from typing import Any, Optional

import boto3

from backend.shared.config import get_settings
from backend.llm_client.base import (
    LLMClient,
    LLMResponse,
    StructuredText,
    ComponentMapping,
    SubstitutionPlan,
    SubstitutionStep,
)
from backend.llm_client.prompts import (
    INTERPRET_OCR_PROMPT,
    MAP_COMPONENTS_PROMPT,
    PLAN_SUBSTITUTION_PROMPT,
    GENERATE_REPORT_PROMPT,
)

logger = logging.getLogger(__name__)


class BedrockClaudeLLM(LLMClient):
    """
    LLM client using Claude on Amazon Bedrock.
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
            config = self.settings.get_boto3_config()
            config["region_name"] = self.settings.ai.bedrock.region
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._client = session.client("bedrock-runtime", **config)
            else:
                self._client = boto3.client("bedrock-runtime", **config)
        
        return self._client
    
    @property
    def model_id(self) -> str:
        """Get the configured LLM model ID."""
        return self.settings.ai.bedrock.llm_model_id
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Generate a completion for a prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system context
            response_schema: Optional JSON schema for output
            
        Returns:
            LLMResponse with completion
        """
        logger.info(f"Generating completion for prompt: {prompt[:100]}...")
        
        try:
            # Build system prompt
            system = system_prompt or "You are an expert assistant for analyzing technical drawings and CAD documents."
            if response_schema:
                system += f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}"
            
            # Build messages
            messages = [{"role": "user", "content": prompt}]
            
            # Call Bedrock
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.settings.ai.bedrock.max_tokens,
                    "temperature": self.settings.ai.bedrock.temperature,
                    "system": system,
                    "messages": messages,
                }),
            )
            
            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [])
            
            if not content:
                return LLMResponse(
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
                    structured_data = self._extract_json(raw_text)
                except Exception as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
            
            return LLMResponse(
                success=True,
                raw_response=raw_text,
                structured_data=structured_data,
                tokens_used=response_body.get("usage", {}).get("output_tokens", 0),
                model_id=self.model_id,
            )
            
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            return LLMResponse(
                success=False,
                raw_response="",
                error=str(e),
                model_id=self.model_id,
            )
    
    async def interpret_ocr(
        self,
        ocr_text: str,
        context: str,
    ) -> StructuredText:
        """
        Clean and interpret OCR output.
        
        Args:
            ocr_text: Raw OCR text
            context: Context about where text was found
            
        Returns:
            StructuredText with interpretation
        """
        prompt = INTERPRET_OCR_PROMPT.format(
            ocr_text=ocr_text,
            context=context,
        )
        
        schema = {
            "type": "object",
            "properties": {
                "cleaned_text": {"type": "string"},
                "interpretation": {"type": "string"},
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "type": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                },
                "confidence": {"type": "number"},
            },
        }
        
        response = await self.complete(prompt, response_schema=schema)
        
        if response.success and response.structured_data:
            data = response.structured_data
            return StructuredText(
                original_text=ocr_text,
                cleaned_text=data.get("cleaned_text", ocr_text),
                interpretation=data.get("interpretation", ""),
                entities=data.get("entities", []),
                confidence=data.get("confidence", 0.5),
            )
        
        return StructuredText(
            original_text=ocr_text,
            cleaned_text=ocr_text,
            interpretation="Failed to interpret",
            confidence=0.0,
        )
    
    async def map_to_components(
        self,
        annotations: list[str],
        catalog_summary: str,
    ) -> list[ComponentMapping]:
        """
        Map text annotations to catalog components.
        
        Args:
            annotations: List of annotation texts
            catalog_summary: Summary of available components
            
        Returns:
            List of ComponentMapping results
        """
        prompt = MAP_COMPONENTS_PROMPT.format(
            annotations=json.dumps(annotations),
            catalog_summary=catalog_summary,
        )
        
        schema = {
            "type": "object",
            "properties": {
                "mappings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "annotation_text": {"type": "string"},
                            "catalog_id": {"type": "string"},
                            "component_type": {"type": "string"},
                            "confidence": {"type": "number"},
                            "reasoning": {"type": "string"},
                            "alternatives": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        
        response = await self.complete(prompt, response_schema=schema)
        
        mappings = []
        if response.success and response.structured_data:
            for m in response.structured_data.get("mappings", []):
                mappings.append(ComponentMapping(
                    annotation_text=m.get("annotation_text", ""),
                    catalog_id=m.get("catalog_id", ""),
                    component_type=m.get("component_type", "unknown"),
                    confidence=m.get("confidence", 0.5),
                    reasoning=m.get("reasoning", ""),
                    alternatives=m.get("alternatives", []),
                ))
        
        return mappings
    
    async def plan_substitution(
        self,
        user_request: str,
        scene_graph_summary: str,
        catalog_summary: str,
    ) -> SubstitutionPlan:
        """
        Generate a substitution plan from user request.
        
        Args:
            user_request: Natural language request
            scene_graph_summary: Summary of current scene graph
            catalog_summary: Available components
            
        Returns:
            SubstitutionPlan with steps
        """
        prompt = PLAN_SUBSTITUTION_PROMPT.format(
            user_request=user_request,
            scene_graph_summary=scene_graph_summary,
            catalog_summary=catalog_summary,
        )
        
        schema = {
            "type": "object",
            "properties": {
                "request_summary": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "target_component_id": {"type": "string"},
                            "target_description": {"type": "string"},
                            "new_specification": {"type": "object"},
                            "reasoning": {"type": "string"},
                        },
                    },
                },
                "warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "estimated_impact": {
                    "type": "object",
                    "properties": {
                        "weight_change_percent": {"type": "number"},
                        "strength_change": {"type": "string"},
                        "cost_change": {"type": "string"},
                    },
                },
            },
        }
        
        response = await self.complete(prompt, response_schema=schema)
        
        if response.success and response.structured_data:
            data = response.structured_data
            steps = [
                SubstitutionStep(
                    action=s.get("action", "replace"),
                    target_component_id=s.get("target_component_id", ""),
                    target_description=s.get("target_description", ""),
                    new_specification=s.get("new_specification", {}),
                    reasoning=s.get("reasoning", ""),
                )
                for s in data.get("steps", [])
            ]
            
            return SubstitutionPlan(
                request_summary=data.get("request_summary", user_request),
                steps=steps,
                warnings=data.get("warnings", []),
                estimated_impact=data.get("estimated_impact", {}),
            )
        
        return SubstitutionPlan(
            request_summary=user_request,
            steps=[],
            warnings=["Failed to generate substitution plan"],
        )
    
    async def generate_report(
        self,
        job_summary: dict,
        scene_graph_summary: dict,
        substitutions: list[dict],
    ) -> str:
        """
        Generate a human-readable report.
        
        Args:
            job_summary: Job processing summary
            scene_graph_summary: Scene graph summary
            substitutions: Applied substitutions
            
        Returns:
            Markdown report text
        """
        prompt = GENERATE_REPORT_PROMPT.format(
            job_summary=json.dumps(job_summary, indent=2),
            scene_graph_summary=json.dumps(scene_graph_summary, indent=2),
            substitutions=json.dumps(substitutions, indent=2),
        )
        
        response = await self.complete(prompt)
        
        if response.success:
            return response.raw_response
        
        return f"# Processing Report\n\nFailed to generate detailed report.\n\nError: {response.error}"
    
    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from text response.
        
        Args:
            text: Response text
            
        Returns:
            Parsed JSON dict
        """
        import re
        
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract from code blocks
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


