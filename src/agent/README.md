# Agent Orchestration Components

This module provides the core orchestration components for the AWS Operations Agent, including caching, retry logic, and input validation.

## Components

### 1. CacheManager

Manages session-based caching of tool execution results to avoid redundant API calls.

**Features:**
- SHA256-based cache key generation from tool name and parameters
- Configurable TTL (default: 1 hour)
- Automatic expiration of stale entries
- Cache statistics reporting

**Usage:**
```python
from src.agent import CacheManager

# Initialize cache manager
cache = CacheManager(session_ttl_seconds=3600)

# Store result
cache.set("route53", {"fqdn": "demo.example.com"}, {"result": "data"})

# Retrieve result
result = cache.get("route53", {"fqdn": "demo.example.com"})

# Clear cache
cache.clear()

# Get statistics
stats = cache.get_cache_stats()
```

### 2. Retry Decorator

Provides exponential backoff retry logic for transient errors (throttling, network issues, service unavailable).

**Features:**
- Automatic detection of transient errors (AWS throttling, connection errors, timeouts)
- Exponential backoff with configurable parameters
- Optional jitter to prevent thundering herd
- Maximum retry limit (default: 3 attempts)

**Usage:**
```python
from src.agent import retry_with_exponential_backoff
from botocore.exceptions import ClientError

@retry_with_exponential_backoff(max_retries=3, base_delay=1.0)
def query_aws_service():
    # Your AWS API call here
    return boto3_client.describe_instances()

# Function will automatically retry on transient errors
result = query_aws_service()
```

### 3. Input Validator

Validates tool input parameters before execution to prevent invalid API calls.

**Supported Validations:**
- FQDN format (RFC 1035 compliant)
- IPv4 address format
- Date/time ranges (ISO format)
- CloudFront distribution IDs
- HTTP status code ranges

**Usage:**
```python
from src.agent import validate_tool_input, ValidationError

try:
    # Validate Route53 tool input
    validate_tool_input("route53", fqdn="demo.example.com")
    
    # Validate Athena CloudFront logs input
    validate_tool_input(
        "athena_cloudfront_logs",
        distribution_id="E285K0Z0YGWJXZ",
        start_date="2024-01-01",
        end_date="2024-01-31",
        status_code_min=400,
        status_code_max=599
    )
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### 4. ToolExecutor

Unified interface that integrates caching, retry logic, and input validation for tool execution.

**Features:**
- Automatic input validation before execution
- Result caching with configurable TTL
- Retry logic with exponential backoff
- Optional disabling of caching or retry

**Usage:**
```python
from src.agent.tool_executor import ToolExecutor

# Initialize executor
executor = ToolExecutor(cache_ttl_seconds=3600)

# Define your tool function
def query_route53(fqdn: str):
    # Your Route53 query logic
    return {"hosted_zone_id": "Z123", "records": [...]}

# Execute tool with all features enabled
result = executor.execute_tool(
    tool_name="route53",
    tool_function=query_route53,
    parameters={"fqdn": "demo.example.com"},
    use_cache=True,
    use_retry=True
)

# Clear cache
executor.clear_cache()

# Get cache statistics
stats = executor.get_cache_stats()
```

## Integration Example

Here's a complete example showing how to use all components together:

```python
from src.agent.tool_executor import ToolExecutor
from src.agent import ValidationError
import boto3

# Initialize executor
executor = ToolExecutor(cache_ttl_seconds=3600)

# Define tool function
def query_route53_records(fqdn: str):
    """Query Route53 for DNS records."""
    client = boto3.client('route53')
    # Your Route53 query logic here
    return {"hosted_zone_id": "Z123", "records": [...]}

# Execute tool
try:
    result = executor.execute_tool(
        tool_name="route53",
        tool_function=query_route53_records,
        parameters={"fqdn": "demo.example.com"}
    )
    print(f"Result: {result}")
except ValidationError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Execution failed: {e}")
```

## Error Handling

### Transient Errors (Automatically Retried)
- AWS Throttling errors
- Service unavailable errors
- Connection errors
- Timeout errors

### Non-Transient Errors (Not Retried)
- Access denied errors
- Invalid parameter errors
- Resource not found errors

### Validation Errors
- Invalid FQDN format
- Invalid IP address format
- Invalid date/time ranges
- Invalid CloudFront distribution IDs

## Testing

Run the test suite:

```bash
# Run all agent tests
pytest tests/unit/test_cache_manager.py tests/unit/test_retry_decorator.py tests/unit/test_input_validator.py tests/unit/test_tool_executor.py -v

# Run with coverage
pytest tests/unit/test_*.py --cov=src/agent --cov-report=html
```

## Configuration

### Cache TTL
Default: 3600 seconds (1 hour)

```python
executor = ToolExecutor(cache_ttl_seconds=1800)  # 30 minutes
```

### Retry Parameters
- `max_retries`: Maximum retry attempts (default: 3)
- `base_delay`: Initial delay in seconds (default: 1.0)
- `max_delay`: Maximum delay in seconds (default: 60.0)
- `exponential_base`: Base for exponential calculation (default: 2.0)
- `jitter`: Add random jitter to delays (default: True)

```python
from src.agent import retry_with_exponential_backoff

@retry_with_exponential_backoff(
    max_retries=5,
    base_delay=2.0,
    max_delay=120.0
)
def my_function():
    pass
```

## Requirements

These components validate inputs according to the following requirements:
- **Requirement 7.4**: Retry with exponential backoff for transient errors
- **Requirement 7.6**: Tool result caching to avoid redundant API calls
- **Requirement 7.7**: Tool input validation before execution
- **Requirement 9.2**: Handle AWS API throttling with retry logic
