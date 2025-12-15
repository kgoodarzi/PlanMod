"""
Cost estimation for AWS cloud services.

Tracks and estimates costs for:
- Amazon Bedrock (VLM/LLM tokens)
- Amazon S3 (storage, requests)
- Amazon DynamoDB (read/write units)
- Amazon Textract (pages processed)
- AWS Lambda (invocations, duration)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class BedrockCosts:
    """Bedrock pricing per 1000 tokens (as of Dec 2024)."""
    
    # Claude 3.5 Sonnet v2
    CLAUDE_35_SONNET_INPUT = 0.003     # $3 per 1M input tokens
    CLAUDE_35_SONNET_OUTPUT = 0.015    # $15 per 1M output tokens
    
    # Claude 3 Haiku (cheaper alternative)
    CLAUDE_3_HAIKU_INPUT = 0.00025     # $0.25 per 1M input tokens
    CLAUDE_3_HAIKU_OUTPUT = 0.00125    # $1.25 per 1M output tokens
    
    # Image tokens (approximate - images converted to tokens)
    # ~1000 tokens per typical drawing image
    IMAGE_TOKENS_ESTIMATE = 1500


@dataclass
class AWSCosts:
    """AWS service pricing estimates."""
    
    # S3 (per GB per month for standard storage)
    S3_STORAGE_PER_GB = 0.023
    S3_PUT_REQUEST_PER_1000 = 0.005
    S3_GET_REQUEST_PER_1000 = 0.0004
    
    # DynamoDB (on-demand)
    DYNAMODB_WRITE_PER_MILLION = 1.25
    DYNAMODB_READ_PER_MILLION = 0.25
    
    # Lambda
    LAMBDA_REQUEST_PER_MILLION = 0.20
    LAMBDA_DURATION_PER_GB_SECOND = 0.0000166667
    
    # Textract
    TEXTRACT_PER_PAGE = 0.0015
    
    # API Gateway
    API_GATEWAY_PER_MILLION = 3.50


@dataclass
class CostItem:
    """Single cost item."""
    
    service: str
    operation: str
    quantity: float
    unit: str
    unit_cost: float
    total_cost: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


@dataclass 
class CostReport:
    """Accumulated cost report."""
    
    job_id: str
    items: list[CostItem] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    @property
    def total_cost(self) -> float:
        """Total estimated cost."""
        return sum(item.total_cost for item in self.items)
    
    @property
    def cost_by_service(self) -> dict[str, float]:
        """Costs grouped by service."""
        by_service: dict[str, float] = {}
        for item in self.items:
            by_service[item.service] = by_service.get(item.service, 0) + item.total_cost
        return by_service
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "total_cost_usd": round(self.total_cost, 6),
            "cost_by_service": {k: round(v, 6) for k, v in self.cost_by_service.items()},
            "items": [
                {
                    "service": item.service,
                    "operation": item.operation,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_cost": item.unit_cost,
                    "total_cost": round(item.total_cost, 6),
                }
                for item in self.items
            ],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }
    
    def format_summary(self) -> str:
        """Format as human-readable summary."""
        lines = [
            "=" * 50,
            "COST ESTIMATION REPORT",
            "=" * 50,
            f"Job ID: {self.job_id}",
            f"Total Estimated Cost: ${self.total_cost:.4f}",
            "",
            "Cost by Service:",
        ]
        
        for service, cost in sorted(self.cost_by_service.items(), key=lambda x: -x[1]):
            lines.append(f"  {service}: ${cost:.4f}")
        
        lines.extend(["", "Detailed Items:"])
        
        for item in self.items:
            lines.append(
                f"  - {item.service}/{item.operation}: "
                f"{item.quantity:.2f} {item.unit} @ ${item.unit_cost:.6f} = ${item.total_cost:.6f}"
            )
        
        lines.append("=" * 50)
        
        return "\n".join(lines)


class CostEstimator:
    """
    Estimates costs for AWS cloud service usage.
    
    Usage:
        estimator = CostEstimator("job-123")
        estimator.add_bedrock_call(input_tokens=1500, output_tokens=300)
        estimator.add_s3_storage(size_bytes=1024*1024)
        report = estimator.get_report()
        print(report.format_summary())
    """
    
    def __init__(self, job_id: str):
        """Initialize cost estimator for a job."""
        self.report = CostReport(job_id=job_id)
    
    def add_bedrock_call(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "claude-3-5-sonnet",
        includes_image: bool = False,
    ):
        """
        Add cost for a Bedrock model invocation.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model identifier
            includes_image: Whether request included an image
        """
        # Estimate image tokens
        if includes_image:
            input_tokens += BedrockCosts.IMAGE_TOKENS_ESTIMATE
        
        # Get rates based on model
        if "haiku" in model.lower():
            input_rate = BedrockCosts.CLAUDE_3_HAIKU_INPUT
            output_rate = BedrockCosts.CLAUDE_3_HAIKU_OUTPUT
        else:
            input_rate = BedrockCosts.CLAUDE_35_SONNET_INPUT
            output_rate = BedrockCosts.CLAUDE_35_SONNET_OUTPUT
        
        # Calculate costs (rates are per 1000 tokens)
        input_cost = (input_tokens / 1000) * input_rate
        output_cost = (output_tokens / 1000) * output_rate
        
        self.report.items.append(CostItem(
            service="Bedrock",
            operation=f"{model} (input)",
            quantity=input_tokens,
            unit="tokens",
            unit_cost=input_rate / 1000,
            total_cost=input_cost,
            metadata={"model": model, "includes_image": includes_image},
        ))
        
        self.report.items.append(CostItem(
            service="Bedrock",
            operation=f"{model} (output)",
            quantity=output_tokens,
            unit="tokens",
            unit_cost=output_rate / 1000,
            total_cost=output_cost,
            metadata={"model": model},
        ))
    
    def add_s3_upload(self, size_bytes: int, num_requests: int = 1):
        """Add cost for S3 upload operations."""
        size_gb = size_bytes / (1024 ** 3)
        
        # Storage cost (prorated for 1 day assuming 30 day month)
        storage_cost = size_gb * AWSCosts.S3_STORAGE_PER_GB / 30
        
        # Request cost
        request_cost = (num_requests / 1000) * AWSCosts.S3_PUT_REQUEST_PER_1000
        
        self.report.items.append(CostItem(
            service="S3",
            operation="storage (daily)",
            quantity=size_bytes / 1024,
            unit="KB",
            unit_cost=AWSCosts.S3_STORAGE_PER_GB / (1024 * 1024 * 30),
            total_cost=storage_cost,
        ))
        
        self.report.items.append(CostItem(
            service="S3",
            operation="PUT requests",
            quantity=num_requests,
            unit="requests",
            unit_cost=AWSCosts.S3_PUT_REQUEST_PER_1000 / 1000,
            total_cost=request_cost,
        ))
    
    def add_s3_download(self, size_bytes: int, num_requests: int = 1):
        """Add cost for S3 download operations."""
        request_cost = (num_requests / 1000) * AWSCosts.S3_GET_REQUEST_PER_1000
        
        self.report.items.append(CostItem(
            service="S3",
            operation="GET requests",
            quantity=num_requests,
            unit="requests",
            unit_cost=AWSCosts.S3_GET_REQUEST_PER_1000 / 1000,
            total_cost=request_cost,
        ))
    
    def add_dynamodb_write(self, num_writes: int = 1):
        """Add cost for DynamoDB write operations."""
        cost = (num_writes / 1_000_000) * AWSCosts.DYNAMODB_WRITE_PER_MILLION
        
        self.report.items.append(CostItem(
            service="DynamoDB",
            operation="write",
            quantity=num_writes,
            unit="WCU",
            unit_cost=AWSCosts.DYNAMODB_WRITE_PER_MILLION / 1_000_000,
            total_cost=cost,
        ))
    
    def add_dynamodb_read(self, num_reads: int = 1):
        """Add cost for DynamoDB read operations."""
        cost = (num_reads / 1_000_000) * AWSCosts.DYNAMODB_READ_PER_MILLION
        
        self.report.items.append(CostItem(
            service="DynamoDB",
            operation="read",
            quantity=num_reads,
            unit="RCU",
            unit_cost=AWSCosts.DYNAMODB_READ_PER_MILLION / 1_000_000,
            total_cost=cost,
        ))
    
    def add_textract_pages(self, num_pages: int):
        """Add cost for Textract OCR processing."""
        cost = num_pages * AWSCosts.TEXTRACT_PER_PAGE
        
        self.report.items.append(CostItem(
            service="Textract",
            operation="detect_text",
            quantity=num_pages,
            unit="pages",
            unit_cost=AWSCosts.TEXTRACT_PER_PAGE,
            total_cost=cost,
        ))
    
    def add_lambda_invocation(
        self,
        duration_ms: int,
        memory_mb: int = 1024,
        num_invocations: int = 1,
    ):
        """Add cost for Lambda function invocation."""
        # Request cost
        request_cost = (num_invocations / 1_000_000) * AWSCosts.LAMBDA_REQUEST_PER_MILLION
        
        # Duration cost (GB-seconds)
        gb_seconds = (memory_mb / 1024) * (duration_ms / 1000) * num_invocations
        duration_cost = gb_seconds * AWSCosts.LAMBDA_DURATION_PER_GB_SECOND
        
        self.report.items.append(CostItem(
            service="Lambda",
            operation="invocation",
            quantity=num_invocations,
            unit="invocations",
            unit_cost=AWSCosts.LAMBDA_REQUEST_PER_MILLION / 1_000_000,
            total_cost=request_cost,
        ))
        
        self.report.items.append(CostItem(
            service="Lambda",
            operation="duration",
            quantity=gb_seconds,
            unit="GB-seconds",
            unit_cost=AWSCosts.LAMBDA_DURATION_PER_GB_SECOND,
            total_cost=duration_cost,
        ))
    
    def add_api_gateway_request(self, num_requests: int = 1):
        """Add cost for API Gateway requests."""
        cost = (num_requests / 1_000_000) * AWSCosts.API_GATEWAY_PER_MILLION
        
        self.report.items.append(CostItem(
            service="API Gateway",
            operation="request",
            quantity=num_requests,
            unit="requests",
            unit_cost=AWSCosts.API_GATEWAY_PER_MILLION / 1_000_000,
            total_cost=cost,
        ))
    
    def finalize(self):
        """Finalize the report with end time."""
        self.report.end_time = datetime.utcnow()
    
    def get_report(self) -> CostReport:
        """Get the cost report."""
        return self.report


# Singleton for tracking costs across a session
_session_estimator: Optional[CostEstimator] = None


def get_session_estimator(job_id: str = "session") -> CostEstimator:
    """Get or create session cost estimator."""
    global _session_estimator
    if _session_estimator is None or _session_estimator.report.job_id != job_id:
        _session_estimator = CostEstimator(job_id)
    return _session_estimator


def reset_session_estimator():
    """Reset session cost estimator."""
    global _session_estimator
    _session_estimator = None


