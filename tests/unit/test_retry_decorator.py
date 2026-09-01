"""Unit tests for retry decorator with exponential backoff."""

import time
import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
from src.agent.retry_decorator import (
    retry_with_exponential_backoff,
    is_transient_error,
    TRANSIENT_ERROR_CODES
)


class TestIsTransientError:
    """Test suite for is_transient_error function."""
    
    def test_throttling_error_is_transient(self):
        """Test that throttling errors are identified as transient."""
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        exception = ClientError(error_response, "DescribeInstances")
        
        assert is_transient_error(exception) is True
    
    def test_service_unavailable_is_transient(self):
        """Test that service unavailable errors are transient."""
        error_response = {
            "Error": {
                "Code": "ServiceUnavailable",
                "Message": "Service temporarily unavailable"
            }
        }
        exception = ClientError(error_response, "DescribeInstances")
        
        assert is_transient_error(exception) is True
    
    def test_connection_error_is_transient(self):
        """Test that connection errors are transient."""
        exception = ConnectionError("Connection failed")
        
        assert is_transient_error(exception) is True
    
    def test_timeout_error_is_transient(self):
        """Test that timeout errors are transient."""
        exception = TimeoutError("Request timed out")
        
        assert is_transient_error(exception) is True
    
    def test_access_denied_is_not_transient(self):
        """Test that access denied errors are not transient."""
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "User not authorized"
            }
        }
        exception = ClientError(error_response, "DescribeInstances")
        
        assert is_transient_error(exception) is False
    
    def test_validation_error_is_not_transient(self):
        """Test that validation errors are not transient."""
        exception = ValueError("Invalid parameter")
        
        assert is_transient_error(exception) is False


class TestRetryDecorator:
    """Test suite for retry_with_exponential_backoff decorator."""
    
    def test_successful_execution_no_retry(self):
        """Test that successful execution doesn't trigger retries."""
        mock_func = Mock(return_value="success")
        decorated_func = retry_with_exponential_backoff()(mock_func)
        
        result = decorated_func()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_transient_error_triggers_retry(self):
        """Test that transient errors trigger retries."""
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        
        mock_func = Mock(side_effect=[
            ClientError(error_response, "DescribeInstances"),
            ClientError(error_response, "DescribeInstances"),
            "success"
        ])
        
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            base_delay=0.1
        )(mock_func)
        
        result = decorated_func()
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_non_transient_error_no_retry(self):
        """Test that non-transient errors don't trigger retries."""
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "User not authorized"
            }
        }
        
        mock_func = Mock(side_effect=ClientError(error_response, "DescribeInstances"))
        decorated_func = retry_with_exponential_backoff()(mock_func)
        
        with pytest.raises(ClientError):
            decorated_func()
        
        assert mock_func.call_count == 1
    
    def test_max_retries_exhausted(self):
        """Test that function fails after max retries are exhausted."""
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        
        mock_func = Mock(side_effect=ClientError(error_response, "DescribeInstances"))
        decorated_func = retry_with_exponential_backoff(
            max_retries=2,
            base_delay=0.1
        )(mock_func)
        
        with pytest.raises(ClientError):
            decorated_func()
        
        # Should be called 3 times (initial + 2 retries)
        assert mock_func.call_count == 3
    
    def test_exponential_backoff_timing(self):
        """Test that delays follow exponential backoff pattern."""
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        
        mock_func = Mock(side_effect=[
            ClientError(error_response, "DescribeInstances"),
            ClientError(error_response, "DescribeInstances"),
            "success"
        ])
        
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            base_delay=0.1,
            jitter=False  # Disable jitter for predictable timing
        )(mock_func)
        
        start_time = time.time()
        result = decorated_func()
        elapsed_time = time.time() - start_time
        
        # Expected delays: 0.1 (first retry) + 0.2 (second retry) = 0.3 seconds
        # Allow some tolerance for execution time
        assert elapsed_time >= 0.3
        assert elapsed_time < 0.5
        assert result == "success"
    
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        
        mock_func = Mock(side_effect=[
            ClientError(error_response, "DescribeInstances"),
            "success"
        ])
        
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            base_delay=10.0,
            max_delay=0.2,
            jitter=False
        )(mock_func)
        
        start_time = time.time()
        result = decorated_func()
        elapsed_time = time.time() - start_time
        
        # Delay should be capped at 0.2 seconds
        assert elapsed_time >= 0.2
        assert elapsed_time < 0.4
        assert result == "success"
    
    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""
        @retry_with_exponential_backoff()
        def sample_function():
            """Sample function docstring."""
            return "result"
        
        assert sample_function.__name__ == "sample_function"
        assert sample_function.__doc__ == "Sample function docstring."
    
    def test_decorator_with_arguments(self):
        """Test that decorator works with functions that have arguments."""
        mock_func = Mock(return_value="success")
        decorated_func = retry_with_exponential_backoff()(mock_func)
        
        result = decorated_func("arg1", "arg2", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")
