"""
Configuration management for PlanMod.

Loads settings from aws_config.yaml and environment variables.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AWSCredentials(BaseModel):
    """AWS authentication credentials."""
    
    region: str = "us-east-1"
    profile: Optional[str] = "default"
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None


class DeploymentConfig(BaseModel):
    """Deployment environment configuration."""
    
    environment: str = "dev"
    stack_prefix: str = "planmod"
    account_id: Optional[str] = None


class StorageConfig(BaseModel):
    """S3 storage configuration."""
    
    bucket_name: str = "storage"
    temp_retention_days: int = 7
    output_retention_days: int = 30
    versioning_enabled: bool = True
    
    def get_full_bucket_name(self, prefix: str, env: str) -> str:
        """Get the full bucket name with prefix and environment."""
        return f"{prefix}-{self.bucket_name}-{env}"


class LambdaConfig(BaseModel):
    """Lambda function configuration."""
    
    memory_mb: int = 1024
    timeout_seconds: int = 300
    reserved_concurrency: int = 0
    architecture: str = "x86_64"


class DynamoDBConfig(BaseModel):
    """DynamoDB configuration."""
    
    billing_mode: str = "PAY_PER_REQUEST"
    read_capacity_units: int = 5
    write_capacity_units: int = 5
    point_in_time_recovery: bool = False


class BedrockConfig(BaseModel):
    """Amazon Bedrock AI configuration."""
    
    vlm_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    llm_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    region: str = "us-east-1"
    max_tokens: int = 4096
    temperature: float = 0.3


class TextractConfig(BaseModel):
    """Amazon Textract configuration."""
    
    features: list[str] = Field(default_factory=lambda: ["TABLES", "FORMS"])
    async_processing: bool = True


class AIConfig(BaseModel):
    """AI services configuration."""
    
    bedrock: BedrockConfig = Field(default_factory=BedrockConfig)
    textract: TextractConfig = Field(default_factory=TextractConfig)


class APIConfig(BaseModel):
    """API Gateway configuration."""
    
    type: str = "REST"
    cors_enabled: bool = True
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    rate_limit: int = 100
    burst_limit: int = 200
    auth_type: str = "API_KEY"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = "INFO"
    retention_days: int = 14
    xray_tracing: bool = True


class CostConfig(BaseModel):
    """Cost management configuration."""
    
    tags: dict[str, str] = Field(
        default_factory=lambda: {"Project": "PlanMod", "Environment": "dev"}
    )
    budget_alert_threshold: float = 50.0


class LocalConfig(BaseModel):
    """Local development configuration."""
    
    api_port: int = 8000
    frontend_port: int = 5173
    debug: bool = True
    use_localstack: bool = False
    localstack_endpoint: str = "http://localhost:4566"


class Settings(BaseSettings):
    """
    Main settings class for PlanMod.
    
    Loads configuration from aws_config.yaml and environment variables.
    Environment variables take precedence over config file values.
    """
    
    aws: AWSCredentials = Field(default_factory=AWSCredentials)
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    lambda_config: LambdaConfig = Field(default_factory=LambdaConfig, alias="lambda")
    dynamodb: DynamoDBConfig = Field(default_factory=DynamoDBConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    local: LocalConfig = Field(default_factory=LocalConfig)
    
    class Config:
        env_prefix = "PLANMOD_"
        env_nested_delimiter = "__"
    
    @property
    def bucket_name(self) -> str:
        """Get the full S3 bucket name."""
        return self.storage.get_full_bucket_name(
            self.deployment.stack_prefix,
            self.deployment.environment
        )
    
    @property
    def is_local(self) -> bool:
        """Check if running in local development mode."""
        return self.local.debug or self.local.use_localstack
    
    def get_boto3_config(self) -> dict[str, Any]:
        """Get boto3 client configuration."""
        config: dict[str, Any] = {"region_name": self.aws.region}
        
        if self.local.use_localstack:
            config["endpoint_url"] = self.local.localstack_endpoint
        
        if self.aws.access_key_id and self.aws.secret_access_key:
            config["aws_access_key_id"] = self.aws.access_key_id
            config["aws_secret_access_key"] = self.aws.secret_access_key
            if self.aws.session_token:
                config["aws_session_token"] = self.aws.session_token
        
        return config


def load_config_file(config_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Looks for config files in order:
    1. Provided path
    2. aws_config.local.yaml (user's local config with secrets)
    3. aws_config.yaml (default config)
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        Configuration dictionary
    """
    # Determine config directory
    project_root = Path(__file__).parent.parent.parent
    config_dir = project_root / "infrastructure" / "config"
    
    # Try config files in order
    config_files = [
        config_path,
        config_dir / "aws_config.local.yaml",
        config_dir / "aws_config.yaml",
    ]
    
    for cfg_file in config_files:
        if cfg_file and cfg_file.exists():
            with open(cfg_file) as f:
                return yaml.safe_load(f) or {}
    
    return {}


@lru_cache()
def get_settings(config_path: Optional[str] = None) -> Settings:
    """
    Get application settings (cached).
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Settings instance
    """
    config_data = load_config_file(Path(config_path) if config_path else None)
    return Settings(**config_data)


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """
    Reload settings, clearing the cache.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Fresh Settings instance
    """
    get_settings.cache_clear()
    return get_settings(config_path)


