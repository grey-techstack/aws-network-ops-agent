"""
AWS CLI Tool for AWS Operations Agent.

This module provides a universal AWS CLI tool that allows the AI agent
to query ANY AWS service without pre-defined functions.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

import json
import logging
from typing import Dict, Any, Optional, Annotated
from langchain_core.tools import tool, InjectedToolArg
from botocore.exceptions import ClientError, ParamValidationError
from datetime import datetime

logger = logging.getLogger(__name__)

# Security: Only allow read-only operations
ALLOWED_OPERATION_PREFIXES = [
    'describe_',
    'list_',
    'get_',
    'query_',
]

BLOCKED_OPERATION_PREFIXES = [
    'create_',
    'delete_',
    'update_',
    'modify_',
    'terminate_',
    'stop_',
    'start_',
    'reboot_',
    'put_',
    'attach_',
    'detach_',
    'associate_',
    'disassociate_',
]


def is_operation_allowed(operation: str) -> bool:
    """
    Check if operation is allowed (read-only).
    
    Args:
        operation: Operation name in snake_case
        
    Returns:
        True if operation is allowed, False otherwise
    """
    # Check if operation starts with blocked prefix
    for prefix in BLOCKED_OPERATION_PREFIXES:
        if operation.startswith(prefix):
            return False
    
    # Check if operation starts with allowed prefix
    for prefix in ALLOWED_OPERATION_PREFIXES:
        if operation.startswith(prefix):
            return True
    
    # Default: block unknown operations
    return False


@tool
def execute_aws_cli_command(
    service: str,
    operation: str,
    parameters: Dict[str, Any],
    credential_manager: Annotated[Any, InjectedToolArg],
    account_id: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Execute AWS CLI command dynamically to query ANY AWS service.
    Use this when you need to query AWS resources that don't have dedicated tools.
    
    SECURITY: Only read-only operations allowed (describe_*, list_*, get_*, query_*)
    
    Args:
        service: AWS service name (e.g., 'elbv2', 'ec2', 'route53', 'rds')
        operation: API operation in snake_case (e.g., 'describe_listeners', 'describe_rules')
        parameters: Dictionary of parameters for the operation
        account_id: AWS account ID (optional, defaults to CORE_NETWORK_ACCOUNT_ID)
        
    Returns:
        JSON with AWS API response
        
    Examples:
        - Query listener rules: service='elbv2', operation='describe_rules', parameters={'ListenerArn': '...'}
        - Query target health: service='elbv2', operation='describe_target_health', parameters={'TargetGroupArn': '...'}
        - Query EC2 instances: service='ec2', operation='describe_instances', parameters={'Filters': [...]}
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info(f"Executing AWS CLI command: {service}.{operation}")
        logger.info(f"Parameters: {json.dumps(parameters, default=str)}")
        
        # Security check: Only allow read-only operations
        if not is_operation_allowed(operation):
            error_msg = f"Operation '{operation}' is not allowed. Only read-only operations are permitted."
            logger.warning(error_msg)
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg,
                "hint": "Only describe_*, list_*, get_*, query_* operations are allowed"
            }
        
        # Normalize account_id
        target_account = account_id
        if not target_account or target_account == 'CORE_NETWORK_ACCOUNT_ID':
            import os
            target_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')
        
        # Get boto3 client for the service
        try:
            client = credential_manager.get_boto3_client(
                service,
                account_id=target_account
            )
        except Exception as e:
            error_msg = f"Failed to create {service} client: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg
            }
        
        # Get the operation method
        if not hasattr(client, operation):
            error_msg = f"Operation '{operation}' not found in {service} service"
            logger.error(error_msg)
            
            # Suggest similar operations
            available_ops = [op for op in dir(client) if not op.startswith('_')]
            suggestions = [op for op in available_ops if operation.replace('_', '') in op.replace('_', '')]
            
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg,
                "suggestions": suggestions[:5] if suggestions else []
            }
        
        # Execute the operation
        try:
            method = getattr(client, operation)
            
            # Use paginator if available for complete results
            paginator_name = operation
            try:
                paginator = client.get_paginator(paginator_name)
                pages = paginator.paginate(**parameters)
                response = {}
                for page in pages:
                    if 'ResponseMetadata' in page:
                        del page['ResponseMetadata']
                    # Merge list results across pages
                    for key, value in page.items():
                        if isinstance(value, list):
                            response.setdefault(key, []).extend(value)
                        elif key not in response:
                            response[key] = value
            except Exception:
                # Fallback to single call if paginator not available
                response = method(**parameters)
                if 'ResponseMetadata' in response:
                    del response['ResponseMetadata']
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={
                    'service': service,
                    'operation': operation,
                    'account_id': target_account
                },
                execution_time_ms=execution_time_ms,
                success=True,
                request_id=request_id,
                result_summary=f"Successfully executed {service}.{operation}"
            )
            
            logger.info(f"Successfully executed {service}.{operation}")
            
            # Add count for list results
            result_count = None
            result_key = None
            for key, value in response.items():
                if isinstance(value, list):
                    result_count = len(value)
                    result_key = key
                    break
            
            # If result is too large (>50 items), return summary + IPs only
            if result_count and result_count > 30 and result_key:
                summary_items = []
                for item in response[result_key]:
                    # Extract key identifiers only
                    summary = {}
                    for k in ['PublicIp', 'AllocationId', 'AssociationId', 'InstanceId', 
                              'NetworkInterfaceId', 'PrivateIpAddress', 'Name', 'Id',
                              'DomainName', 'DistributionId', 'LoadBalancerArn', 'LoadBalancerName',
                              'InstanceId', 'SubnetId', 'VpcId']:
                        if k in item:
                            summary[k] = item[k]
                    # Extract Name from Tags
                    if 'Tags' in item and isinstance(item['Tags'], list):
                        for tag in item['Tags']:
                            if tag.get('Key') == 'Name':
                                summary['Name'] = tag.get('Value')
                                break
                    summary_items.append(summary)
                response[result_key] = summary_items
            
            result = {
                "success": True,
                "service": service,
                "operation": operation,
                "account_id": target_account,
                "result": response,
                "total_count": result_count,
                "execution_time_ms": execution_time_ms
            }
            
            return result
            
        except ParamValidationError as e:
            error_msg = f"Invalid parameters for {service}.{operation}: {str(e)}"
            logger.error(error_msg)
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={'service': service, 'operation': operation},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_msg
            )
            
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg,
                "hint": "Check AWS CLI/boto3 documentation for correct parameter format"
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            
            logger.error(f"AWS API error: {error_code} - {error_msg}")
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={'service': service, 'operation': operation},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=f"{error_code}: {error_msg}"
            )
            
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": f"{error_code}: {error_msg}",
                "error_code": error_code
            }
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Error executing AWS CLI command: {error_msg}", exc_info=True)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={'service': service, 'operation': operation},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_msg
            )
        except ImportError:
            pass
        
        return {
            "success": False,
            "service": service,
            "operation": operation,
            "error": error_msg
        }
