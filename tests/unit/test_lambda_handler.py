"""Unit tests for Lambda handler."""

import json
import pytest
from src.lambda_handler import lambda_handler


@pytest.mark.unit
def test_lambda_handler_missing_query(lambda_context):
    """Test Lambda handler with missing query parameter."""
    event = {
        "body": json.dumps({})
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "query" in body["error"]


@pytest.mark.unit
def test_lambda_handler_valid_query(lambda_context):
    """Test Lambda handler with valid query."""
    event = {
        "body": json.dumps({
            "query": "Trace demo.example.com",
            "session_id": "test-session-123"
        })
    }
    
    response = lambda_handler(event, lambda_context)
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["query"] == "Trace demo.example.com"
    assert body["session_id"] == "test-session-123"
