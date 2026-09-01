"""
Amazon Bedrock LLM client configuration for the AWS Operations Agent.

This module provides a configured ChatBedrock instance for use with LangChain agents.
"""

import os
import logging
from typing import Optional
from langchain_aws import ChatBedrock
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockClientError(Exception):
    """Exception raised for Bedrock client errors."""
    pass


def create_bedrock_llm(
    model_id: Optional[str] = None,
    region_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    credentials: Optional[dict] = None
) -> ChatBedrock:
    """
    Create and configure a ChatBedrock LLM instance.
    
    Args:
        model_id: Bedrock model ID (default: us.anthropic.claude-sonnet-4-20250514-v1:0)
        region_name: AWS region (default: us-east-1 for cross-region inference, or from environment)
        temperature: Model temperature for response randomness (0.0 = deterministic)
        max_tokens: Maximum tokens in response
        credentials: Optional AWS credentials dict with AccessKeyId, SecretAccessKey, SessionToken
        
    Returns:
        Configured ChatBedrock instance
        
    Raises:
        BedrockClientError: If Bedrock client creation fails
        
    Environment Variables:
        BEDROCK_MODEL_ID: Override default model ID
        BEDROCK_REGION: Override default region
        AWS_REGION: Fallback region if BEDROCK_REGION not set
    """
    # Get model ID from parameter, environment, or use default
    if model_id is None:
        model_id = os.environ.get(
            "BEDROCK_MODEL_ID",
            "us.amazon.nova-pro-v1:0"  # Nova Pro - best balance of speed & reasoning (Premier timeouts in Lambda)
        )
    
    # Get region from parameter, environment, or use us-east-1
    # Must use US region for us.* cross-region inference profiles
    if region_name is None:
        region_name = os.environ.get(
            "BEDROCK_REGION",
            "us-east-1"  # US region for us.* inference profiles
        )
    
    logger.info(
        f"Creating Bedrock LLM client: model={model_id}, "
        f"region={region_name}, temperature={temperature}, max_tokens={max_tokens}"
    )
    
    try:
        # Build model kwargs
        model_kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Create ChatBedrock instance
        llm = ChatBedrock(
            model_id=model_id,
            region_name=region_name,
            model_kwargs=model_kwargs,
            credentials_profile_name=None,
        )
        
        # If credentials provided, configure them
        if credentials:
            import boto3
            session = boto3.Session(
                aws_access_key_id=credentials.get("AccessKeyId"),
                aws_secret_access_key=credentials.get("SecretAccessKey"),
                aws_session_token=credentials.get("SessionToken"),
                region_name=region_name
            )
            llm = ChatBedrock(
                model_id=model_id,
                region_name=region_name,
                model_kwargs=model_kwargs,
                client=session.client("bedrock-runtime")
            )
        
        logger.info("Bedrock LLM client created successfully")
        return llm
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        
        logger.error(
            f"Failed to create Bedrock client: {error_code} - {error_message}"
        )
        
        if error_code == "AccessDeniedException":
            raise BedrockClientError(
                f"Access denied to Bedrock service. "
                f"Ensure the IAM role has 'bedrock:InvokeModel' permission for model {model_id}. "
                f"Error: {error_message}"
            )
        elif error_code == "ResourceNotFoundException":
            raise BedrockClientError(
                f"Bedrock model not found: {model_id}. "
                f"Ensure the model ID is correct and available in region {region_name}. "
                f"Error: {error_message}"
            )
        elif error_code == "ThrottlingException":
            raise BedrockClientError(
                f"Bedrock API throttled. Please retry after a delay. "
                f"Error: {error_message}"
            )
        else:
            raise BedrockClientError(
                f"Failed to create Bedrock client: {error_code} - {error_message}"
            )
    except Exception as e:
        logger.error(f"Unexpected error creating Bedrock client: {str(e)}")
        raise BedrockClientError(f"Unexpected error: {str(e)}")
