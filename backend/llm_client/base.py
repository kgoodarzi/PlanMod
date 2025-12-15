"""
Base LLM client interface.

Defines the abstract interface for large language model clients.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StructuredText:
    """Result of OCR text interpretation."""
    
    original_text: str
    cleaned_text: str
    interpretation: str
    entities: list[dict] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class ComponentMapping:
    """Mapping from annotation to catalog component."""
    
    annotation_text: str
    catalog_id: str
    component_type: str
    confidence: float
    reasoning: str
    alternatives: list[str] = field(default_factory=list)


@dataclass
class SubstitutionStep:
    """A single step in a substitution plan."""
    
    action: str  # replace, resize, remove, add
    target_component_id: str
    target_description: str
    new_specification: dict
    reasoning: str


@dataclass
class SubstitutionPlan:
    """Plan for component substitutions."""
    
    request_summary: str
    steps: list[SubstitutionStep]
    warnings: list[str] = field(default_factory=list)
    estimated_impact: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from LLM processing."""
    
    success: bool
    raw_response: str
    structured_data: Optional[Any] = None
    error: Optional[str] = None
    tokens_used: int = 0
    model_id: str = ""


class LLMClient(ABC):
    """
    Abstract base class for Large Language Model clients.
    
    Implementations should provide access to an LLM for:
    - Interpreting OCR text
    - Mapping annotations to components
    - Planning substitutions
    - Generating reports
    """
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass


