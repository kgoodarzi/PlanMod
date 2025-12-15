"""
VLM (Vision-Language Model) client module for PlanMod.

Provides abstracted access to vision-language models for image analysis.
"""

from backend.vlm_client.base import VLMClient, VLMResponse
from backend.vlm_client.bedrock_claude import BedrockClaudeVLM

__all__ = [
    "VLMClient",
    "VLMResponse",
    "BedrockClaudeVLM",
]


