"""Tool executor that integrates caching, retry logic, and input validation."""

import logging
from typing import Any, Callable, Dict, Optional
from .cache_manager import CacheManager
from .retry_decorator import retry_with_exponential_backoff
from .input_validator import validate_tool_input, ValidationError


logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tools with integrated caching, retry logic, and input validation.
    
    This class provides a unified interface for executing tools with:
    - Input validation before execution
    - Result caching to avoid redundant API calls
    - Automatic retry with exponential backoff for transient errors
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Initialize the tool executor.
        
        Args:
            cache_ttl_seconds: Time-to-live for cache entries in seconds (default: 1 hour)
        """
        self.cache_manager = CacheManager(session_ttl_seconds=cache_ttl_seconds)
    
    def execute_tool(
        self,
        tool_name: str,
        tool_function: Callable,
        parameters: Dict[str, Any],
        use_cache: bool = True,
        use_retry: bool = True
    ) -> Any:
        """
        Execute a tool with validation, caching, and retry logic.
        
        Args:
            tool_name: Name of the tool being executed
            tool_function: The actual tool function to execute
            parameters: Parameters to pass to the tool
            use_cache: Whether to use caching (default: True)
            use_retry: Whether to use retry logic (default: True)
            
        Returns:
            Tool execution result
            
        Raises:
            ValidationError: If input validation fails
            Exception: If tool execution fails after retries
        """
        # Step 1: Validate inputs
        logger.info(f"Validating inputs for tool: {tool_name}")
        validate_tool_input(tool_name, **parameters)
        
        # Step 2: Check cache
        if use_cache:
            cached_result = self.cache_manager.get(tool_name, parameters)
            if cached_result is not None:
                logger.info(f"Cache hit for tool: {tool_name}")
                return cached_result
            logger.info(f"Cache miss for tool: {tool_name}")
        
        # Step 3: Execute tool (with retry if enabled)
        if use_retry:
            # Wrap the tool function with retry decorator
            retryable_function = retry_with_exponential_backoff(
                max_retries=3,
                base_delay=1.0,
                max_delay=60.0
            )(tool_function)
            result = retryable_function(**parameters)
        else:
            result = tool_function(**parameters)
        
        # Step 4: Cache result
        if use_cache:
            logger.info(f"Caching result for tool: {tool_name}")
            self.cache_manager.set(tool_name, parameters, result)
        
        return result
    
    def clear_cache(self) -> None:
        """Clear all cached tool results."""
        self.cache_manager.clear()
        logger.info("Tool cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        return self.cache_manager.get_cache_stats()
