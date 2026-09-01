"""Unit tests for ToolExecutor integration."""

import pytest
from unittest.mock import Mock
from botocore.exceptions import ClientError
from src.agent.tool_executor import ToolExecutor
from src.agent.input_validator import ValidationError


class TestToolExecutor:
    """Test suite for ToolExecutor class."""
    
    def test_successful_tool_execution(self):
        """Test successful tool execution with caching."""
        executor = ToolExecutor()
        
        # Mock tool function
        mock_tool = Mock(return_value={"result": "success"})
        
        # Execute tool
        result = executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        assert result == {"result": "success"}
        assert mock_tool.call_count == 1
    
    def test_cache_hit_avoids_execution(self):
        """Test that cached results avoid re-execution."""
        executor = ToolExecutor()
        
        # Mock tool function
        mock_tool = Mock(return_value={"result": "success"})
        
        # First execution
        result1 = executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        # Second execution (should use cache)
        result2 = executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        assert result1 == result2
        assert mock_tool.call_count == 1  # Only called once
    
    def test_input_validation_failure(self):
        """Test that invalid inputs raise ValidationError."""
        executor = ToolExecutor()
        
        # Mock tool function (should not be called)
        mock_tool = Mock(return_value={"result": "success"})
        
        # Execute with invalid FQDN
        with pytest.raises(ValidationError):
            executor.execute_tool(
                tool_name="route53",
                tool_function=mock_tool,
                parameters={"fqdn": "invalid_fqdn"}
            )
        
        # Tool should not have been called
        assert mock_tool.call_count == 0
    
    def test_retry_on_transient_error(self):
        """Test that transient errors trigger retry."""
        executor = ToolExecutor()
        
        # Mock tool function that fails once then succeeds
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        mock_tool = Mock(side_effect=[
            ClientError(error_response, "DescribeInstances"),
            {"result": "success"}
        ])
        
        # Execute tool
        result = executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        assert result == {"result": "success"}
        assert mock_tool.call_count == 2  # Called twice (initial + 1 retry)
    
    def test_cache_disabled(self):
        """Test that caching can be disabled."""
        executor = ToolExecutor()
        
        # Mock tool function
        mock_tool = Mock(return_value={"result": "success"})
        
        # First execution
        result1 = executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"},
            use_cache=False
        )
        
        # Second execution (should not use cache)
        result2 = executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"},
            use_cache=False
        )
        
        assert result1 == result2
        assert mock_tool.call_count == 2  # Called twice
    
    def test_retry_disabled(self):
        """Test that retry can be disabled."""
        executor = ToolExecutor()
        
        # Mock tool function that always fails
        error_response = {
            "Error": {
                "Code": "Throttling",
                "Message": "Rate exceeded"
            }
        }
        mock_tool = Mock(side_effect=ClientError(error_response, "DescribeInstances"))
        
        # Execute tool with retry disabled
        with pytest.raises(ClientError):
            executor.execute_tool(
                tool_name="route53",
                tool_function=mock_tool,
                parameters={"fqdn": "demo.example.com"},
                use_retry=False
            )
        
        # Should only be called once (no retries)
        assert mock_tool.call_count == 1
    
    def test_clear_cache(self):
        """Test that cache can be cleared."""
        executor = ToolExecutor()
        
        # Mock tool function
        mock_tool = Mock(return_value={"result": "success"})
        
        # Execute tool
        executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        # Clear cache
        executor.clear_cache()
        
        # Execute again (should not use cache)
        executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        assert mock_tool.call_count == 2
    
    def test_get_cache_stats(self):
        """Test cache statistics reporting."""
        executor = ToolExecutor()
        
        # Mock tool function
        mock_tool = Mock(return_value={"result": "success"})
        
        # Execute tool
        executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo.example.com"}
        )
        
        # Get stats
        stats = executor.get_cache_stats()
        
        assert stats["total_entries"] == 1
        assert stats["active_entries"] == 1
    
    def test_different_parameters_no_cache_hit(self):
        """Test that different parameters don't result in cache hits."""
        executor = ToolExecutor()
        
        # Mock tool function
        mock_tool = Mock(return_value={"result": "success"})
        
        # Execute with first FQDN
        executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo1.example.com"}
        )
        
        # Execute with second FQDN
        executor.execute_tool(
            tool_name="route53",
            tool_function=mock_tool,
            parameters={"fqdn": "demo2.example.com"}
        )
        
        # Should be called twice (different parameters)
        assert mock_tool.call_count == 2
