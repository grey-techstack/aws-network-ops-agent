"""
Integration tests for error handling scenarios.

These tests validate the error handling workflow including:
- Invalid SSO role ARN handling
- Missing F5 credentials handling
- Throttled AWS API calls handling
- F5 API unavailable handling

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""
import sys
from unittest.mock import Mock, MagicMock

# Mock langchain modules before importing
mock_langchain_aws = MagicMock()
mock_langchain_aws.ChatBedrock = MagicMock()
sys.modules['langchain_aws'] = mock_langchain_aws

import json
import os
import pytest
from unittest.mock import patch
from src.agent.error_handlers import (
    ErrorHandler,
    AgentError,
    AuthenticationError,
    AWSAPIError,
    F5WAFError,
    NetworkError,
    handle_error
)


class TestErrorHandlingIntegration:
    """Integration tests for error handling functionality."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        env = {
            'SSO_ROLE_ARN': 'arn:aws:iam::123456789012:role/GlobalReaderRole',
            'F5_SECRET_NAME': 'f5-api-credentials',
            'CORE_NETWORK_ACCOUNT_ID': '111111111111',
            'WORKLOAD_ACCOUNT_IDS': '222222222222',
        }
        with patch.dict(os.environ, env):
            yield env

    # Test invalid SSO role ARN (Requirement 9.1)
    def test_invalid_sso_role_arn_access_denied(self):
        """Test handling of invalid SSO role ARN with access denied (Req 9.1)."""
        error = Exception("AccessDenied: User is not authorized to perform sts:AssumeRole")
        result = ErrorHandler.handle_authentication_error(
            error,
            component="assume SSO role",
            role_arn="arn:aws:iam::123456789012:role/InvalidRole"
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "authentication"
        assert "Access denied" in result["error_message"]
        assert "troubleshooting_steps" in result["error_details"]
        assert len(result["error_details"]["troubleshooting_steps"]) > 0

    def test_invalid_sso_role_arn_reports_permissions(self):
        """Test that invalid SSO role reports required permissions (Req 9.1)."""
        error = Exception("AccessDenied: User is not authorized to perform sts:AssumeRole")
        result = ErrorHandler.handle_authentication_error(
            error,
            component="assume SSO role",
            role_arn="arn:aws:iam::123456789012:role/InvalidRole"
        )
        
        assert "required_permissions" in result["error_details"]
        # Should suggest checking IAM policies
        troubleshooting = result["error_details"]["troubleshooting_steps"]
        assert any("IAM" in step for step in troubleshooting)

    def test_expired_credentials_handling(self):
        """Test handling of expired credentials."""
        error = Exception("ExpiredToken: The security token included in the request is expired")
        result = ErrorHandler.handle_authentication_error(
            error,
            component="AWS API call"
        )
        
        assert result["status"] == "error"
        assert "expired" in result["error_message"].lower()
        assert "automatically refreshed" in str(result["error_details"]["troubleshooting_steps"]).lower()

    # Test missing F5 credentials (Requirement 9.4)
    def test_missing_f5_credentials_unauthorized(self):
        """Test handling of missing F5 credentials (Req 9.4)."""
        error = Exception("401 Unauthorized: Invalid API credentials")
        result = ErrorHandler.handle_f5_waf_error(
            error,
            operation="query F5 WAF config",
            fqdn="demo.example.com"
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "f5_waf"
        assert "authentication failed" in result["error_message"].lower()
        assert "Secrets Manager" in str(result["error_details"]["troubleshooting_steps"])

    def test_f5_credentials_graceful_degradation(self):
        """Test F5 credentials error allows graceful degradation (Req 9.4)."""
        error = Exception("401 Unauthorized")
        result = ErrorHandler.handle_f5_waf_error(
            error,
            operation="query F5 WAF config",
            fqdn="demo.example.com"
        )
        
        assert "graceful_degradation" in result["error_details"]
        assert "AWS resource tracing will continue" in result["error_details"]["graceful_degradation"]

    # Test throttled AWS API calls (Requirement 9.2)
    def test_throttled_aws_api_calls(self):
        """Test handling of throttled AWS API calls (Req 9.2)."""
        error = Mock()
        error.response = {'Error': {'Code': 'Throttling'}}
        error.__str__ = lambda self: "Throttling: Rate exceeded"
        
        result = ErrorHandler.handle_aws_api_error(
            error,
            service="Route53",
            operation="ListResourceRecordSets"
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "aws_api"
        assert "throttled" in result["error_message"].lower()
        assert "exponential backoff" in str(result["error_details"]["troubleshooting_steps"]).lower()

    def test_throttled_api_suggests_retry(self):
        """Test throttled API error suggests automatic retry (Req 9.2)."""
        error = Mock()
        error.response = {'Error': {'Code': 'TooManyRequestsException'}}
        error.__str__ = lambda self: "TooManyRequestsException"
        
        result = ErrorHandler.handle_aws_api_error(
            error,
            service="CloudFront",
            operation="ListDistributions"
        )
        
        troubleshooting = result["error_details"]["troubleshooting_steps"]
        assert any("retry" in step.lower() for step in troubleshooting)



    def test_f5_api_unavailable(self):
        """Test handling of F5 API unavailable (Req 9.4)."""
        error = Exception("503 Service Unavailable")
        result = ErrorHandler.handle_f5_waf_error(
            error,
            operation="query F5 WAF config",
            fqdn="demo.example.com"
        )
        
        assert result["status"] == "error"
        assert "unavailable" in result["error_message"].lower()
        assert "skipped" in str(result["error_details"]["troubleshooting_steps"]).lower()

    def test_f5_api_unavailable_continues_aws_tracing(self):
        """Test F5 API unavailable allows AWS tracing to continue (Req 9.4)."""
        error = Exception("503 Service Unavailable")
        result = ErrorHandler.handle_f5_waf_error(
            error,
            operation="query F5 WAF config"
        )
        
        assert "graceful_degradation" in result["error_details"]
        assert "AWS" in result["error_details"]["graceful_degradation"]

    # Test network errors (Requirement 9.5)
    def test_network_connection_timeout(self):
        """Test handling of network connection timeout (Req 9.5)."""
        error = Exception("Connection timed out")
        result = ErrorHandler.handle_network_error(
            error,
            target="api.example.com",
            operation="HTTP request"
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "network"
        assert "timeout" in result["error_message"].lower()

    def test_network_dns_resolution_failure(self):
        """Test handling of DNS resolution failure (Req 9.5)."""
        error = Exception("getaddrinfo failed: Name or service not known")
        result = ErrorHandler.handle_network_error(
            error,
            target="invalid.hostname.com",
            operation="DNS lookup"
        )
        
        assert "DNS" in result["error_message"]
        troubleshooting = result["error_details"]["troubleshooting_steps"]
        assert any("hostname" in step.lower() or "dns" in step.lower() for step in troubleshooting)

    def test_network_ssl_error(self):
        """Test handling of SSL/TLS error."""
        error = Exception("SSL: CERTIFICATE_VERIFY_FAILED")
        result = ErrorHandler.handle_network_error(
            error,
            target="secure.example.com",
            operation="HTTPS request"
        )
        
        assert "SSL" in result["error_message"] or "TLS" in result["error_message"]

    # Test sensitive information protection (Requirement 9.7)
    def test_sensitive_info_not_exposed_in_errors(self):
        """Test sensitive information is not exposed in errors (Req 9.7)."""
        error = Exception("AccessDenied with aws_access_key_id=AKIAIOSFODNN7EXAMPLE")
        result = ErrorHandler.handle_authentication_error(
            error,
            component="AWS API call"
        )
        
        # Check that access key is sanitized
        original_error = result["error_details"]["original_error"]
        assert "AKIAIOSFODNN7EXAMPLE" not in original_error
        assert "***" in original_error

    def test_internal_ips_sanitized(self):
        """Test internal IPs are sanitized in error messages (Req 9.7)."""
        error = Exception("Connection failed to 10.0.1.100:8080")
        result = ErrorHandler.handle_network_error(
            error,
            target="internal-service",
            operation="connect"
        )
        
        original_error = result["error_details"]["original_error"]
        assert "10.0.1.100" not in original_error
        assert "INTERNAL_IP" in original_error

    def test_api_keys_sanitized(self):
        """Test API keys are sanitized in error messages (Req 9.7)."""
        error = Exception("Authentication failed with api_key=secret123456")
        result = ErrorHandler.handle_f5_waf_error(
            error,
            operation="F5 API call"
        )
        
        original_error = result["error_details"]["original_error"]
        assert "secret123456" not in original_error

    # Test partial results with errors (Requirement 9.8)
    def test_partial_results_with_errors(self):
        """Test partial results are returned with errors (Req 9.8)."""
        partial_results = {
            "route53": {"records": [{"type": "A", "value": "1.2.3.4"}]},
            "cloudfront": {"distribution_id": "E123"}
        }
        errors = [
            {"error_type": "f5_waf", "error_message": "F5 API unavailable"}
        ]
        
        result = ErrorHandler.create_partial_result_response(
            partial_results=partial_results,
            errors=errors,
            operation="FQDN tracing"
        )
        
        assert result["status"] == "partial"
        assert "partial_results" in result
        assert "errors" in result
        assert len(result["errors"]) == 1
        assert result["partial_results"]["route53"]["records"][0]["type"] == "A"

    # Test AWS API permission errors (Requirement 9.1)
    def test_aws_api_permission_denied(self):
        """Test AWS API permission denied error (Req 9.1)."""
        error = Mock()
        error.response = {'Error': {'Code': 'AccessDenied'}}
        error.__str__ = lambda self: "AccessDenied: User is not authorized"
        
        result = ErrorHandler.handle_aws_api_error(
            error,
            service="ELB",
            operation="DescribeLoadBalancers"
        )
        
        assert "Permission denied" in result["error_message"]
        assert "ELB" in result["error_message"]
        troubleshooting = result["error_details"]["troubleshooting_steps"]
        assert any("permission" in step.lower() for step in troubleshooting)

    def test_aws_api_resource_not_found(self):
        """Test AWS API resource not found error."""
        error = Mock()
        error.response = {'Error': {'Code': 'ResourceNotFoundException'}}
        error.__str__ = lambda self: "ResourceNotFoundException"
        
        result = ErrorHandler.handle_aws_api_error(
            error,
            service="CloudFront",
            operation="GetDistribution",
            resource="E123456789"
        )
        
        assert "not found" in result["error_message"].lower()
        assert result["error_details"]["resource"] == "E123456789"

    # Test unexpected errors (Requirement 9.6)
    def test_unexpected_error_logging(self):
        """Test unexpected errors are logged properly (Req 9.6)."""
        error = Exception("Unexpected internal error")
        result = ErrorHandler.handle_unexpected_error(
            error,
            component="agent_orchestrator",
            operation="execute_query",
            context={"query": "test query"}
        )
        
        assert result["status"] == "error"
        assert result["error_type"] == "unexpected"
        assert "stack_trace" in result["error_details"]
        assert "logged" in str(result["error_details"]["troubleshooting_steps"]).lower()

    # Test error response structure
    def test_error_response_has_timestamp(self):
        """Test all error responses include timestamp."""
        error = Exception("Test error")
        result = ErrorHandler.handle_authentication_error(error, component="test")
        
        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO format

    def test_error_response_has_error_type(self):
        """Test all error responses include error type."""
        error = Exception("Test error")
        
        auth_result = ErrorHandler.handle_authentication_error(error, component="test")
        assert auth_result["error_type"] == "authentication"
        
        f5_result = ErrorHandler.handle_f5_waf_error(error, operation="test")
        assert f5_result["error_type"] == "f5_waf"

    # Test handle_error dispatcher
    def test_handle_error_dispatcher(self):
        """Test handle_error function dispatches to correct handler."""
        error = Exception("Test error")
        
        result = handle_error(error, "authentication", component="test")
        assert result["error_type"] == "authentication"
        
        result = handle_error(error, "f5_waf", operation="test")
        assert result["error_type"] == "f5_waf"

    def test_handle_error_unknown_type(self):
        """Test handle_error handles unknown error types."""
        error = Exception("Test error")
        result = handle_error(error, "unknown_type", component="test", operation="test")
        assert result["error_type"] == "unexpected"
