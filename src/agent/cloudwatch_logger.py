"""
CloudWatch logging module for AWS Operations Agent.

This module provides comprehensive logging functionality including:
- Operation logging with timestamps
- Cross-account access logging
- Tool execution logging
- Error logging with stack traces
- Sensitive information filtering
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive information from log messages."""
    
    # Patterns for sensitive data
    SENSITIVE_PATTERNS = [
        # AWS credentials
        (r'(aws_access_key_id|AccessKeyId)["\s:=]+([A-Z0-9]{20})', r'\1=***REDACTED***'),
        (r'(aws_secret_access_key|SecretAccessKey)["\s:=]+([A-Za-z0-9/+=]{40})', r'\1=***REDACTED***'),
        (r'(aws_session_token|SessionToken)["\s:=]+([A-Za-z0-9/+=]{100,})', r'\1=***REDACTED***'),
        
        # API keys and tokens
        (r'(api[_-]?key|token|password)["\s:=]+([^\s"&]+)', r'\1=***REDACTED***'),
        
        # Private IP addresses
        (r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b', 
         '***PRIVATE_IP***'),
        
        # Account IDs (12-digit numbers that might be account IDs)
        (r'\b\d{12}\b', '***ACCOUNT_ID***'),
        
        # ARNs (keep structure but redact account ID)
        (r'(arn:aws:[^:]+:[^:]*:)(\d{12})(:.*)', r'\1***ACCOUNT_ID***\3'),
    ]
    
    def filter(self, record):
        """Filter sensitive data from log record."""
        if hasattr(record, 'msg') and record.msg:
            message = str(record.msg)
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
            record.msg = message
        
        # Also filter args if present
        if hasattr(record, 'args') and record.args:
            filtered_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    filtered_arg = arg
                    for pattern, replacement in self.SENSITIVE_PATTERNS:
                        filtered_arg = re.sub(pattern, replacement, filtered_arg, flags=re.IGNORECASE)
                    filtered_args.append(filtered_arg)
                else:
                    filtered_args.append(arg)
            record.args = tuple(filtered_args)
        
        return True


class CloudWatchLogger:
    """Enhanced logger for AWS Operations Agent with structured logging."""
    
    def __init__(self, logger_name: str = __name__):
        """Initialize the CloudWatch logger."""
        self.logger = logging.getLogger(logger_name)
        
        # Add sensitive data filter if not already present
        if not any(isinstance(f, SensitiveDataFilter) for f in self.logger.filters):
            self.logger.addFilter(SensitiveDataFilter())
    
    def log_operation_start(
        self,
        operation: str,
        request_id: str,
        user_query: Optional[str] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None
    ) -> None:
        """Log the start of an operation."""
        log_data = {
            'event_type': 'operation_start',
            'operation': operation,
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'source_ip': source_ip
        }
        
        if user_query:
            # Log only first 200 characters of query for privacy
            log_data['user_query_preview'] = user_query[:200] + ('...' if len(user_query) > 200 else '')
        
        self.logger.info(f"Operation started: {json.dumps(log_data)}")
    
    def log_operation_complete(
        self,
        operation: str,
        request_id: str,
        execution_time_ms: int,
        success: bool,
        result_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Log the completion of an operation."""
        log_data = {
            'event_type': 'operation_complete',
            'operation': operation,
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat(),
            'execution_time_ms': execution_time_ms,
            'success': success,
            'result_type': result_type
        }
        
        if error_message:
            log_data['error_message'] = error_message
        
        level = logging.INFO if success else logging.ERROR
        self.logger.log(level, f"Operation completed: {json.dumps(log_data)}")
    
    def log_cross_account_access(
        self,
        operation: str,
        source_account: str,
        target_account: str,
        role_arn: str,
        success: bool,
        request_id: str,
        error_message: Optional[str] = None
    ) -> None:
        """Log cross-account access attempts."""
        log_data = {
            'event_type': 'cross_account_access',
            'operation': operation,
            'source_account': source_account,
            'target_account': target_account,
            'role_arn': role_arn,
            'success': success,
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if error_message:
            log_data['error_message'] = error_message
        
        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"Cross-account access: {json.dumps(log_data)}")
    
    def log_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        execution_time_ms: int,
        success: bool,
        request_id: str,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Log tool execution details."""
        # Sanitize parameters to remove sensitive data
        sanitized_params = self._sanitize_parameters(parameters)
        
        log_data = {
            'event_type': 'tool_execution',
            'tool_name': tool_name,
            'parameters': sanitized_params,
            'execution_time_ms': execution_time_ms,
            'success': success,
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if result_summary:
            log_data['result_summary'] = result_summary
        
        if error_message:
            log_data['error_message'] = error_message
        
        level = logging.INFO if success else logging.ERROR
        self.logger.log(level, f"Tool execution: {json.dumps(log_data)}")
    
    def log_error_with_context(
        self,
        error: Exception,
        operation: str,
        context: Dict[str, Any],
        request_id: str,
        include_stack_trace: bool = True
    ) -> None:
        """Log error with full context and stack trace."""
        import traceback
        
        # Sanitize context to remove sensitive data
        sanitized_context = self._sanitize_parameters(context)
        
        log_data = {
            'event_type': 'error',
            'error_type': type(error).__name__,
            'error_message': str(error),
            'operation': operation,
            'context': sanitized_context,
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if include_stack_trace:
            stack_trace = traceback.format_exc()
            # Apply sensitive data filtering to stack trace
            for pattern, replacement in SensitiveDataFilter.SENSITIVE_PATTERNS:
                stack_trace = re.sub(pattern, replacement, stack_trace, flags=re.IGNORECASE)
            log_data['stack_trace'] = stack_trace
        
        self.logger.error(f"Error occurred: {json.dumps(log_data)}")
    
    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters to remove sensitive information."""
        if not isinstance(params, dict):
            return params
        
        sanitized = {}
        for key, value in params.items():
            key_lower = key.lower()
            
            # Check if key indicates sensitive data
            if any(sensitive in key_lower for sensitive in [
                'password', 'secret', 'key', 'token', 'credential'
            ]):
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_parameters(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_parameters(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, str):
                # Apply string sanitization patterns
                sanitized_value = value
                for pattern, replacement in SensitiveDataFilter.SENSITIVE_PATTERNS:
                    sanitized_value = re.sub(pattern, replacement, sanitized_value, flags=re.IGNORECASE)
                sanitized[key] = sanitized_value
            else:
                sanitized[key] = value
        
        return sanitized


# Global logger instance
cloudwatch_logger = CloudWatchLogger()