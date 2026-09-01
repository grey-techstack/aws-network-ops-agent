"""
Error handlers for AWS Operations Agent.

This module provides comprehensive error handling for:
- Authentication errors (SSO role assumption, F5 credentials)
- AWS API errors (throttling, permissions, not found, service unavailable)
- Athena errors (timeout, syntax, permissions)
- F5 WAF errors (unavailable, authentication)
- Network errors (connection timeout, DNS, SSL/TLS)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import traceback


class AgentError(Exception):
    """Base exception for agent errors."""
    
    def __init__(self, message: str, error_type: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()


class AuthenticationError(AgentError):
    """Exception for authentication failures."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "authentication", details)


class AWSAPIError(AgentError):
    """Exception for AWS API errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "aws_api", details)


class AthenaError(AgentError):
    """Exception for Athena query errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "athena", details)


class F5WAFError(AgentError):
    """Exception for F5 WAF API errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "f5_waf", details)


class NetworkError(AgentError):
    """Exception for network errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "network", details)


class ErrorHandler:
    """Comprehensive error handler for the AWS Operations Agent."""
    
    @staticmethod
    def handle_authentication_error(
        error: Exception,
        component: str,
        account_id: Optional[str] = None,
        role_arn: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle authentication errors."""
        error_message = str(error)
        
        if "AccessDenied" in error_message or "not authorized" in error_message.lower():
            user_message = f"Access denied when attempting to {component}"
            required_permissions = ErrorHandler._extract_required_permissions(error_message, component)
            troubleshooting = [
                f"Verify the Lambda execution role has permissions to {component}",
                "Check IAM policies attached to the execution role",
                "Verify trust relationships are configured correctly"
            ]
            if role_arn:
                troubleshooting.append(f"Verify the role {role_arn} exists and is assumable")
            
        elif "ExpiredToken" in error_message or "expired" in error_message.lower():
            user_message = "Authentication credentials have expired"
            required_permissions = []
            troubleshooting = [
                "Credentials will be automatically refreshed on next request",
                "If issue persists, check STS session duration settings"
            ]
            
        elif "InvalidClientTokenId" in error_message:
            user_message = "Invalid AWS credentials"
            required_permissions = []
            troubleshooting = [
                "Verify AWS credentials are configured correctly",
                "Check that the Lambda execution role exists"
            ]
            
        else:
            user_message = f"Authentication error in {component}: {error_message}"
            required_permissions = []
            troubleshooting = [
                "Check CloudWatch Logs for detailed error information",
                "Verify all IAM roles and policies are configured correctly"
            ]
        
        return {
            "status": "error",
            "error_type": "authentication",
            "error_message": user_message,
            "error_details": {
                "component": component,
                "account_id": account_id,
                "role_arn": role_arn,
                "required_permissions": required_permissions,
                "troubleshooting_steps": troubleshooting,
                "original_error": ErrorHandler._sanitize_error_message(error_message)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_aws_api_error(
        error: Exception,
        service: str,
        operation: str,
        resource: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle AWS API errors."""
        error_message = str(error)
        error_code = getattr(error, 'response', {}).get('Error', {}).get('Code', 'Unknown')
        
        if error_code in ['Throttling', 'ThrottlingException', 'TooManyRequestsException']:
            user_message = f"{service} API is being throttled"
            troubleshooting = [
                "Request will be automatically retried with exponential backoff",
                "If issue persists, consider implementing request batching"
            ]
            
        elif error_code in ['AccessDenied', 'UnauthorizedOperation', 'AccessDeniedException']:
            user_message = f"Permission denied for {service} {operation}"
            troubleshooting = [
                f"Verify the assumed role has {service} permissions",
                f"Required action: {service}:{operation}",
                "Check IAM policies for the assumed role"
            ]
            
        elif error_code in ['ResourceNotFoundException', 'NoSuchEntity', 'NotFound']:
            user_message = f"{service} resource not found"
            troubleshooting = [
                f"Verify the resource exists: {resource}" if resource else "Verify the resource exists",
                "Check if the resource is in the correct AWS account"
            ]
            
        elif error_code in ['ServiceUnavailable', 'InternalError', 'InternalFailure']:
            user_message = f"{service} service is temporarily unavailable"
            troubleshooting = [
                "Request will be automatically retried",
                "Check AWS Service Health Dashboard for service status"
            ]
            
        else:
            user_message = f"{service} API error: {error_code}"
            troubleshooting = [
                "Check CloudWatch Logs for detailed error information",
                f"Verify {service} API parameters are correct"
            ]
        
        return {
            "status": "error",
            "error_type": "aws_api",
            "error_message": user_message,
            "error_details": {
                "service": service,
                "operation": operation,
                "resource": resource,
                "error_code": error_code,
                "required_permissions": ErrorHandler._extract_required_permissions(error_message, service),
                "troubleshooting_steps": troubleshooting,
                "original_error": ErrorHandler._sanitize_error_message(error_message)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_athena_error(
        error: Exception,
        query_type: str,
        query_execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle Athena query errors."""
        error_message = str(error)
        
        if "timeout" in error_message.lower() or "exceeded" in error_message.lower():
            user_message = "Athena query timed out"
            troubleshooting = [
                "Try reducing the time range for the query",
                "Add more specific filters to reduce data scanned",
                "Consider partitioning the data by date"
            ]
            
        elif "syntax" in error_message.lower() or "parse" in error_message.lower():
            user_message = "Athena query syntax error"
            troubleshooting = [
                "Query syntax is automatically generated - this may indicate a bug",
                "Check CloudWatch Logs for the full query",
                "Verify the Athena table schema matches expected format"
            ]
            
        elif "access denied" in error_message.lower() or "not authorized" in error_message.lower():
            user_message = "Permission denied for Athena query"
            troubleshooting = [
                "Verify the assumed role has Athena query permissions",
                "Verify the role has S3 read permissions for the data location",
                "Verify the role has S3 write permissions for query results"
            ]
            
        elif "result set" in error_message.lower() and "large" in error_message.lower():
            user_message = "Athena query result set is too large"
            troubleshooting = [
                "Add more specific filters to reduce result size",
                "Reduce the time range for the query",
                "Results will be automatically paginated if possible"
            ]
            
        else:
            user_message = f"Athena query error: {error_message}"
            troubleshooting = [
                "Check CloudWatch Logs for detailed error information",
                "Verify Athena database and table exist"
            ]
        
        return {
            "status": "error",
            "error_type": "athena",
            "error_message": user_message,
            "error_details": {
                "query_type": query_type,
                "query_execution_id": query_execution_id,
                "troubleshooting_steps": troubleshooting,
                "original_error": ErrorHandler._sanitize_error_message(error_message)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_f5_waf_error(
        error: Exception,
        operation: str,
        fqdn: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle F5 WAF API errors."""
        error_message = str(error)
        
        if "401" in error_message or "unauthorized" in error_message.lower():
            user_message = "F5 WAF API authentication failed"
            troubleshooting = [
                "Verify F5 API credentials in AWS Secrets Manager",
                "Check if F5 API credentials have expired",
                "Contact F5 administrator to verify API access"
            ]
            
        elif "503" in error_message or "unavailable" in error_message.lower():
            user_message = "F5 WAF API is unavailable"
            troubleshooting = [
                "F5 WAF checks will be skipped for this request",
                "AWS resource tracing will continue",
                "Check F5 Distributed Cloud status page"
            ]
            
        elif "429" in error_message or "rate limit" in error_message.lower():
            user_message = "F5 WAF API rate limit exceeded"
            troubleshooting = [
                "Request will be retried after a delay",
                "Consider implementing request caching"
            ]
            
        elif "404" in error_message or "not found" in error_message.lower():
            user_message = f"F5 WAF configuration not found for {fqdn}" if fqdn else "F5 WAF resource not found"
            troubleshooting = [
                "Verify the FQDN is configured in F5 Distributed Cloud",
                "AWS resource tracing will continue without F5 data"
            ]
            
        else:
            user_message = f"F5 WAF API error: {error_message}"
            troubleshooting = [
                "F5 WAF checks will be skipped for this request",
                "Check CloudWatch Logs for detailed error information"
            ]
        
        return {
            "status": "error",
            "error_type": "f5_waf",
            "error_message": user_message,
            "error_details": {
                "operation": operation,
                "fqdn": fqdn,
                "troubleshooting_steps": troubleshooting,
                "original_error": ErrorHandler._sanitize_error_message(error_message),
                "graceful_degradation": "AWS resource tracing will continue without F5 data"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_network_error(
        error: Exception,
        target: str,
        operation: str
    ) -> Dict[str, Any]:
        """Handle network errors."""
        error_message = str(error)
        
        if "timeout" in error_message.lower() or "timed out" in error_message.lower():
            user_message = f"Connection timeout to {target}"
            troubleshooting = [
                "Request will be automatically retried",
                "Check network connectivity",
                "Verify security group rules allow outbound connections"
            ]
            
        elif "dns" in error_message.lower() or "getaddrinfo" in error_message.lower():
            user_message = f"DNS resolution failed for {target}"
            troubleshooting = [
                "Verify the hostname is correct",
                "Check DNS configuration in VPC"
            ]
            
        elif "ssl" in error_message.lower() or "tls" in error_message.lower():
            user_message = f"SSL/TLS error connecting to {target}"
            troubleshooting = [
                "Verify SSL certificate is valid",
                "Check if certificate has expired"
            ]
            
        elif "connection refused" in error_message.lower():
            user_message = f"Connection refused by {target}"
            troubleshooting = [
                "Verify the service is running",
                "Check if the port is correct",
                "Verify security group rules allow the connection"
            ]
            
        else:
            user_message = f"Network error connecting to {target}: {error_message}"
            troubleshooting = [
                "Request will be automatically retried",
                "Check CloudWatch Logs for detailed error information"
            ]
        
        return {
            "status": "error",
            "error_type": "network",
            "error_message": user_message,
            "error_details": {
                "target": target,
                "operation": operation,
                "troubleshooting_steps": troubleshooting,
                "original_error": ErrorHandler._sanitize_error_message(error_message)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def handle_unexpected_error(
        error: Exception,
        component: str,
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle unexpected errors with detailed logging."""
        error_message = str(error)
        stack_trace = traceback.format_exc()
        
        user_message = f"Unexpected error in {component} during {operation}"
        
        return {
            "status": "error",
            "error_type": "unexpected",
            "error_message": user_message,
            "error_details": {
                "component": component,
                "operation": operation,
                "context": context or {},
                "troubleshooting_steps": [
                    "This error has been logged for investigation",
                    "Check CloudWatch Logs for detailed stack trace",
                    "Contact support if issue persists"
                ],
                "original_error": ErrorHandler._sanitize_error_message(error_message),
                "stack_trace": ErrorHandler._sanitize_stack_trace(stack_trace)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_partial_result_response(
        partial_results: Dict[str, Any],
        errors: List[Dict[str, Any]],
        operation: str
    ) -> Dict[str, Any]:
        """Create a response with partial results and errors."""
        return {
            "status": "partial",
            "message": f"{operation} completed with some errors",
            "partial_results": partial_results,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _extract_required_permissions(error_message: str, service: str) -> List[str]:
        """Extract required permissions from error message."""
        permissions = []
        
        action_pattern = r'(?:action|permission):\\s*([a-zA-Z0-9:*]+)'
        matches = re.findall(action_pattern, error_message, re.IGNORECASE)
        permissions.extend(matches)
        
        service_permissions = {
            "STS": ["sts:AssumeRole"],
            "Route53": ["route53:ListHostedZones", "route53:ListResourceRecordSets"],
            "CloudFront": ["cloudfront:ListDistributions", "cloudfront:GetDistribution"],
            "ELB": ["elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeTargetGroups"],
            "Athena": ["athena:StartQueryExecution", "athena:GetQueryExecution", "s3:GetObject", "s3:PutObject"],
            "Secrets Manager": ["secretsmanager:GetSecretValue"]
        }
        
        if service in service_permissions and not permissions:
            permissions = service_permissions[service]
        
        return permissions
    
    @staticmethod
    def _sanitize_error_message(error_message: str) -> str:
        """Sanitize error message to remove sensitive information."""
        sanitized = re.sub(r'(aws_access_key_id|aws_secret_access_key|session_token)=[^\\s&]+', r'\\1=***', error_message, flags=re.IGNORECASE)
        sanitized = re.sub(r'(api[_-]?key|token|password)[\\s:=]+[^\\s&]+', r'\\1=***', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'\\b(?:10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|172\\.(?:1[6-9]|2\\d|3[01])\\.\\d{1,3}\\.\\d{1,3}|192\\.168\\.\\d{1,3}\\.\\d{1,3})\\b', '***INTERNAL_IP***', sanitized)
        
        return sanitized
    
    @staticmethod
    def _sanitize_stack_trace(stack_trace: str) -> str:
        """Sanitize stack trace to remove sensitive information."""
        return ErrorHandler._sanitize_error_message(stack_trace)


def handle_error(error: Exception, error_type: str, **kwargs) -> Dict[str, Any]:
    """Handle an error based on its type."""
    if error_type == "authentication":
        return ErrorHandler.handle_authentication_error(error, **kwargs)
    elif error_type == "aws_api":
        return ErrorHandler.handle_aws_api_error(error, **kwargs)
    elif error_type == "athena":
        return ErrorHandler.handle_athena_error(error, **kwargs)
    elif error_type == "f5_waf":
        return ErrorHandler.handle_f5_waf_error(error, **kwargs)
    elif error_type == "network":
        return ErrorHandler.handle_network_error(error, **kwargs)
    else:
        return ErrorHandler.handle_unexpected_error(error, **kwargs)
