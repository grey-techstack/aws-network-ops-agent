"""
CloudFront Tool for AWS Operations Agent.

This module provides a LangChain tool for querying CloudFront distributions.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

from langchain_core.tools import tool, InjectedToolArg
from typing import Dict, Any, Optional, Annotated
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


@tool
def query_cloudfront_distribution(
    credential_manager: Annotated[Any, InjectedToolArg],
    distribution_id: Optional[str] = None,
    domain_name: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query CloudFront distribution details by distribution ID or domain name.
    Use this tool to get CloudFront CDN configuration and origin details.
    
    Args:
        distribution_id: CloudFront distribution ID (e.g., E123ABC)
        domain_name: Domain name to search for (e.g., demo.example.com)
        
    Returns:
        JSON with distribution details, aliases, and origin configurations
    """
    try:
        logger.info(f"Querying CloudFront distribution - ID: {distribution_id}, Domain: {domain_name}")
        
        # Get CloudFront client
        cloudfront_client = credential_manager.get_boto3_client('cloudfront')
        
        # Find distribution by ID or domain name
        if distribution_id:
            distribution = _get_distribution_by_id(cloudfront_client, distribution_id)
        elif domain_name:
            distribution = _find_distribution_by_domain(cloudfront_client, domain_name)
        else:
            return {
                "error": "Either distribution_id or domain_name must be provided"
            }
        
        if not distribution:
            error_msg = f"Distribution not found for ID: {distribution_id}" if distribution_id else f"Distribution not found for domain: {domain_name}"
            logger.warning(error_msg)
            return {
                "distribution_id": distribution_id,
                "domain_name": domain_name,
                "aliases": [],
                "origins": [],
                "status": None,
                "error": error_msg
            }
        
        # Extract distribution details
        result = _extract_distribution_details(distribution)
        
        logger.info(f"Successfully retrieved CloudFront distribution: {result['distribution_id']}")
        return result
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"CloudFront API error: {error_code} - {error_message}")
        
        return {
            "distribution_id": distribution_id,
            "domain_name": domain_name,
            "aliases": [],
            "origins": [],
            "status": None,
            "error": f"CloudFront API error: {error_code} - {error_message}"
        }
    
    except Exception as e:
        logger.error(f"Unexpected error querying CloudFront: {str(e)}")
        return {
            "distribution_id": distribution_id,
            "domain_name": domain_name,
            "aliases": [],
            "origins": [],
            "status": None,
            "error": f"Unexpected error: {str(e)}"
        }


def _get_distribution_by_id(
    cloudfront_client,
    distribution_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get CloudFront distribution by ID.
    
    Args:
        cloudfront_client: boto3 CloudFront client
        distribution_id: CloudFront distribution ID
        
    Returns:
        Distribution dictionary or None if not found
    """
    try:
        response = cloudfront_client.get_distribution(Id=distribution_id)
        return response['Distribution']
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchDistribution':
            logger.warning(f"Distribution not found: {distribution_id}")
            return None
        raise


def _find_distribution_by_domain(
    cloudfront_client,
    domain_name: str
) -> Optional[Dict[str, Any]]:
    """
    Find CloudFront distribution by domain name (alias or CloudFront domain).
    
    Args:
        cloudfront_client: boto3 CloudFront client
        domain_name: Domain name to search for
        
    Returns:
        Distribution dictionary or None if not found
    """
    try:
        # List all distributions
        paginator = cloudfront_client.get_paginator('list_distributions')
        
        for page in paginator.paginate():
            if 'DistributionList' not in page or 'Items' not in page['DistributionList']:
                continue
            
            for dist_summary in page['DistributionList']['Items']:
                # Check if domain matches CloudFront domain name
                if dist_summary['DomainName'] == domain_name:
                    # Get full distribution details
                    return _get_distribution_by_id(cloudfront_client, dist_summary['Id'])
                
                # Check if domain matches any alias
                if 'Aliases' in dist_summary and 'Items' in dist_summary['Aliases']:
                    if domain_name in dist_summary['Aliases']['Items']:
                        # Get full distribution details
                        return _get_distribution_by_id(cloudfront_client, dist_summary['Id'])
        
        return None
        
    except ClientError as e:
        logger.error(f"Error listing distributions: {e}")
        return None


def _extract_distribution_details(distribution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant details from a CloudFront distribution.
    
    Args:
        distribution: CloudFront distribution dictionary
        
    Returns:
        Formatted distribution details
    """
    dist_config = distribution['DistributionConfig']
    
    # Extract aliases
    aliases = []
    if 'Aliases' in dist_config and 'Items' in dist_config['Aliases']:
        aliases = dist_config['Aliases']['Items']
    
    # Extract origins
    origins = []
    if 'Origins' in dist_config and 'Items' in dist_config['Origins']:
        for origin in dist_config['Origins']['Items']:
            origin_info = {
                "id": origin['Id'],
                "domain_name": origin['DomainName']
            }
            
            # Add origin protocol policy if available
            if 'CustomOriginConfig' in origin:
                origin_info['origin_protocol_policy'] = origin['CustomOriginConfig'].get('OriginProtocolPolicy', 'unknown')
            elif 'S3OriginConfig' in origin:
                origin_info['origin_protocol_policy'] = 's3'
            else:
                origin_info['origin_protocol_policy'] = 'unknown'
            
            # Add connection settings
            if 'CustomOriginConfig' in origin:
                custom_config = origin['CustomOriginConfig']
                origin_info['http_port'] = custom_config.get('HTTPPort', 80)
                origin_info['https_port'] = custom_config.get('HTTPSPort', 443)
            
            origins.append(origin_info)
    
    return {
        "distribution_id": distribution['Id'],
        "domain_name": distribution['DomainName'],
        "aliases": aliases,
        "origins": origins,
        "status": distribution['Status'],
        "enabled": dist_config.get('Enabled', False),
        "comment": dist_config.get('Comment', '')
    }


class CloudFrontTool:
    """
    Wrapper class for CloudFront tool that maintains credential manager reference.
    """
    
    def __init__(self, credential_manager):
        """
        Initialize CloudFront tool with credential manager.
        
        Args:
            credential_manager: CredentialManager instance
        """
        self.credential_manager = credential_manager
    
    def query_distribution(
        self,
        distribution_id: Optional[str] = None,
        domain_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query CloudFront distribution details.
        
        Args:
            distribution_id: CloudFront distribution ID (optional)
            domain_name: Domain name to search for (optional)
            
        Returns:
            Dictionary with distribution information
        """
        return query_cloudfront_distribution(
            self.credential_manager,
            distribution_id=distribution_id,
            domain_name=domain_name
        )
