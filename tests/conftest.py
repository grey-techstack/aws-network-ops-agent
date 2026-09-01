"""Pytest configuration and shared fixtures."""

import pytest
from hypothesis import settings, Verbosity

# Configure Hypothesis for property-based testing
settings.register_profile("default", max_examples=100, deadline=None)
settings.register_profile("ci", max_examples=1000, deadline=None)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.verbose)
settings.load_profile("default")


@pytest.fixture
def mock_aws_credentials(monkeypatch):
    """Mock AWS credentials for testing."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")



@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    class MockLambdaContext:
        function_name = "aws-ops-agent"
        memory_limit_in_mb = 512
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:aws-ops-agent"
        aws_request_id = "test-request-id"
        log_group_name = "/aws/lambda/aws-ops-agent"
        log_stream_name = "2025/01/07/test-stream"
        
        def get_remaining_time_in_millis(self):
            return 300000
    
    return MockLambdaContext()
