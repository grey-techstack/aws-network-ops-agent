"""
Integration tests for FQDN tracing end-to-end functionality.

These tests validate the complete FQDN tracing workflow including:
- F5 WAF discovery
- Route53 DNS record lookup
- CloudFront distribution discovery
- ALB/NLB discovery across accounts
- Hierarchical output formatting
- Partial configuration handling
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.lambda_handler import lambda_handler
from src.agent.agent_orchestrator import AgentOrchestrator
from src.credentials.credential_manager import CredentialManager


class TestFQDNTracingIntegration:
    """Integration tests for FQDN tracing functionality."""
    
    @pytest.fixture
    def mock_environment_variables(self):
        """Mock environment variables for testing."""
        env_vars = {
            'SSO_ROLE_ARN': 'arn:aws:iam::123456789012:role/GlobalReaderRole',
            'F5_SECRET_NAME': 'f5-api-credentials',
            'CORE_NETWORK_ACCOUNT_ID': '111111111111',
            'WORKLOAD_ACCOUNT_IDS': '222222222222,333333333333',
            'ATHENA_DATABASE': 'centralized_logging',
            'ATHENA_OUTPUT_BUCKET': 'aws-ops-agent-athena-results'
        }
        
        with patch.dict(os.environ, env_vars):
            yield env_vars
    
    @pytest.fixture
    def mock_credential_manager(self):
        """Mock credential manager for testing."""
        mock_cm = Mock(spec=CredentialManager)
        mock_cm.get_boto3_client.return_value = Mock()
        return mock_cm
    
    @pytest.fixture
    def sample_fqdn_trace_response(self):
        """Sample complete FQDN trace response."""
        return {
            "fqdn": "demo.example.com",
            "trace_path": [
                {
                    "layer": "F5 WAF",
                    "resource": "example-lb.ac.vh.ves.io",
                    "details": {
                        "load_balancer_name": "demo-lb",
                        "namespace": "production",
                        "domains": ["demo.example.com"],
                        "origin_pools": [
                            {
                                "name": "aws-origin-pool",
                                "origins": [
                                    {
                                        "public_name": "d111111abcdef8.cloudfront.net",
                                        "port": 443
                                    }
                                ]
                            }
                        ]
                    }
                },
                {
                    "layer": "Route53",
                    "resource": "demo.example.com",
                    "details": {
                        "hosted_zone_id": "Z1234567890ABC",
                        "records": [
                            {
                                "type": "ALIAS",
                                "value": "d111111abcdef8.cloudfront.net",
                                "ttl": 300
                            }
                        ]
                    }
                },
                {
                    "layer": "CloudFront",
                    "resource": "E285K0Z0YGWJXZ",
                    "details": {
                        "distribution_id": "E285K0Z0YGWJXZ",
                        "domain_name": "d111111abcdef8.cloudfront.net",
                        "aliases": ["demo.example.com"],
                        "origins": [
                            {
                                "id": "core-alb-origin",
                                "domain_name": "core-alb-123.us-east-1.elb.amazonaws.com",
                                "origin_protocol_policy": "https-only"
                            }
                        ],
                        "status": "Deployed"
                    }
                },
                {
                    "layer": "Core Network ALB",
                    "resource": "core-alb-123.us-east-1.elb.amazonaws.com",
                    "details": {
                        "load_balancer_arn": "arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/app/core-alb/1234567890abcdef",
                        "load_balancer_name": "core-alb",
                        "type": "application",
                        "scheme": "internet-facing",
                        "vpc_id": "vpc-12345678",
                        "account_id": "111111111111",
                        "target_groups": [
                            {
                                "target_group_name": "workload-tg",
                                "protocol": "HTTPS",
                                "port": 443,
                                "targets": [
                                    {
                                        "id": "workload-alb-456.us-east-1.elb.amazonaws.com",
                                        "port": 443,
                                        "health_status": "healthy"
                                    }
                                ]
                            }
                        ]
                    }
                },
                {
                    "layer": "Workload ALB",
                    "resource": "workload-alb-456.us-east-1.elb.amazonaws.com",
                    "details": {
                        "load_balancer_arn": "arn:aws:elasticloadbalancing:us-east-1:222222222222:loadbalancer/app/workload-alb/abcdef1234567890",
                        "load_balancer_name": "workload-alb",
                        "type": "application",
                        "scheme": "internal",
                        "vpc_id": "vpc-87654321",
                        "account_id": "222222222222",
                        "target_groups": [
                            {
                                "target_group_name": "backend-tg",
                                "protocol": "HTTP",
                                "port": 8080,
                                "targets": [
                                    {
                                        "id": "10.0.1.100",
                                        "port": 8080,
                                        "health_status": "healthy"
                                    },
                                    {
                                        "id": "10.0.1.101",
                                        "port": 8080,
                                        "health_status": "healthy"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
    
    @pytest.fixture
    def sample_partial_trace_response(self):
        """Sample partial FQDN trace response (missing F5 WAF)."""
        return {
            "fqdn": "simple.example.com",
            "trace_path": [
                {
                    "layer": "Route53",
                    "resource": "simple.example.com",
                    "details": {
                        "hosted_zone_id": "Z9876543210DEF",
                        "records": [
                            {
                                "type": "A",
                                "value": "203.0.113.63",
                                "ttl": 300
                            }
                        ]
                    }
                },
                {
                    "layer": "ALB",
                    "resource": "simple-alb-789.us-west-2.elb.amazonaws.com",
                    "details": {
                        "load_balancer_arn": "arn:aws:elasticloadbalancing:us-west-2:111111111111:loadbalancer/app/simple-alb/fedcba0987654321",
                        "load_balancer_name": "simple-alb",
                        "type": "application",
                        "scheme": "internet-facing",
                        "vpc_id": "vpc-abcdef12",
                        "account_id": "111111111111",
                        "target_groups": [
                            {
                                "target_group_name": "simple-tg",
                                "protocol": "HTTP",
                                "port": 80,
                                "targets": [
                                    {
                                        "id": "10.0.2.100",
                                        "port": 80,
                                        "health_status": "healthy"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ],
            "warnings": [
                "F5 WAF configuration not found for simple.example.com",
                "CloudFront distribution not found for simple.example.com"
            ]
        }

    def test_complete_fqdn_trace_via_lambda_handler(
        self, 
        mock_environment_variables, 
        sample_fqdn_trace_response
    ):
        """Test complete FQDN tracing through Lambda handler."""
        # Mock the agent orchestrator to return our sample response
        with patch('src.lambda_handler.AgentOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.execute_query.return_value = {
                'success': True,
                'output': json.dumps(sample_fqdn_trace_response),
                'intermediate_steps': [
                    ('query_route53_records', 'Found Route53 records for demo.example.com'),
                    ('query_cloudfront_distribution', 'Found CloudFront distribution E285K0Z0YGWJXZ'),
                    ('query_load_balancer', 'Found ALB in core network account'),
                    ('query_load_balancer', 'Found ALB in workload account')
                ]
            }
            mock_orchestrator_class.return_value = mock_orchestrator
            
            # Mock credential manager initialization
            with patch('src.lambda_handler.CredentialManager') as mock_cm_class:
                mock_cm_class.return_value = Mock()
                
                # Create test event
                event = {
                    'httpMethod': 'POST',
                    'body': json.dumps({
                        'query': 'Trace demo.example.com',
                        'session_id': 'test-session-123'
                    }),
                    'requestContext': {
                        'requestId': 'test-request-123',
                        'identity': {'sourceIp': '192.168.1.100'}
                    }
                }
                
                # Mock Lambda context
                context = Mock()
                context.get_remaining_time_in_millis.return_value = 300000  # 5 minutes
                
                # Execute Lambda handler
                response = lambda_handler(event, context)
                
                # Verify response structure
                assert response['statusCode'] == 200
                
                body = json.loads(response['body'])
                assert body['status'] == 'success'
                assert body['result_type'] == 'fqdn_trace'
                assert 'demo.example.com' in body['output']
                assert body['query'] == 'Trace demo.example.com'
                assert body['session_id'] == 'test-session-123'
                assert 'timestamp' in body
                assert 'execution_time_ms' in body
                
                # Verify agent was called correctly
                mock_orchestrator.execute_query.assert_called_once_with(
                    query='Trace demo.example.com',
                    session_id='test-session-123',
                    request_id='test-request-123'
                )

    def test_partial_fqdn_trace_via_lambda_handler(
        self, 
        mock_environment_variables, 
        sample_partial_trace_response
    ):
        """Test partial FQDN tracing (missing some components) through Lambda handler."""
        # Mock the agent orchestrator to return partial response
        with patch('src.lambda_handler.AgentOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.execute_query.return_value = {
                'success': True,
                'output': json.dumps(sample_partial_trace_response),
                'intermediate_steps': [
                    ('query_route53_records', 'Found Route53 records for simple.example.com'),
                    ('query_cloudfront_distribution', 'No CloudFront distribution found'),
                    ('query_load_balancer', 'Found ALB in core network account')
                ]
            }
            mock_orchestrator_class.return_value = mock_orchestrator
            
            # Mock credential manager initialization
            with patch('src.lambda_handler.CredentialManager') as mock_cm_class:
                mock_cm_class.return_value = Mock()
                
                # Create test event
                event = {
                    'httpMethod': 'POST',
                    'body': json.dumps({
                        'query': 'Trace simple.example.com',
                        'session_id': 'test-session-456'
                    }),
                    'requestContext': {
                        'requestId': 'test-request-456',
                        'identity': {'sourceIp': '192.168.1.101'}
                    }
                }
                
                # Mock Lambda context
                context = Mock()
                context.get_remaining_time_in_millis.return_value = 300000
                
                # Execute Lambda handler
                response = lambda_handler(event, context)
                
                # Verify response structure
                assert response['statusCode'] == 200
                
                body = json.loads(response['body'])
                assert body['status'] == 'success'
                assert 'simple.example.com' in body['output']
                assert body['query'] == 'Trace simple.example.com'
                
                # Verify partial results are handled gracefully
                output_data = json.loads(body['output'])
                assert 'warnings' in output_data
                assert len(output_data['warnings']) > 0
                assert 'F5 WAF configuration not found' in output_data['warnings'][0]

    def test_hierarchical_output_format(self, sample_fqdn_trace_response):
        """Test that FQDN trace output follows hierarchical format."""
        trace_data = sample_fqdn_trace_response
        
        # Verify hierarchical structure
        assert 'fqdn' in trace_data
        assert 'trace_path' in trace_data
        assert isinstance(trace_data['trace_path'], list)
        
        # Verify each layer has required fields
        for layer in trace_data['trace_path']:
            assert 'layer' in layer
            assert 'resource' in layer
            assert 'details' in layer
            assert isinstance(layer['details'], dict)
        
        # Verify expected layer order (F5 WAF -> Route53 -> CloudFront -> ALB -> Workload ALB)
        expected_layers = ['F5 WAF', 'Route53', 'CloudFront', 'Core Network ALB', 'Workload ALB']
        actual_layers = [layer['layer'] for layer in trace_data['trace_path']]
        
        assert actual_layers == expected_layers
        
        # Verify F5 WAF details structure
        f5_layer = trace_data['trace_path'][0]
        assert f5_layer['layer'] == 'F5 WAF'
        assert 'load_balancer_name' in f5_layer['details']
        assert 'namespace' in f5_layer['details']
        assert 'domains' in f5_layer['details']
        assert 'origin_pools' in f5_layer['details']
        
        # Verify Route53 details structure
        route53_layer = trace_data['trace_path'][1]
        assert route53_layer['layer'] == 'Route53'
        assert 'hosted_zone_id' in route53_layer['details']
        assert 'records' in route53_layer['details']
        
        # Verify CloudFront details structure
        cf_layer = trace_data['trace_path'][2]
        assert cf_layer['layer'] == 'CloudFront'
        assert 'distribution_id' in cf_layer['details']
        assert 'origins' in cf_layer['details']
        
        # Verify ALB details structure
        alb_layer = trace_data['trace_path'][3]
        assert alb_layer['layer'] == 'Core Network ALB'
        assert 'load_balancer_arn' in alb_layer['details']
        assert 'target_groups' in alb_layer['details']

    def test_fqdn_trace_with_agent_orchestrator_directly(self, mock_credential_manager):
        """Test FQDN tracing directly through AgentOrchestrator."""
        # Mock the LLM and tools
        with patch('src.agent.agent_orchestrator.create_bedrock_llm') as mock_llm_factory:
            mock_llm = Mock()
            mock_llm_factory.return_value = mock_llm
            
            # Mock tool responses
            with patch('src.tools.query_route53_records') as mock_route53:
                with patch('src.tools.query_cloudfront_distribution') as mock_cf:
                    with patch('src.tools.query_load_balancer') as mock_elb:
                        
                        # Configure mock responses
                        mock_route53.return_value = {
                            "hosted_zone_id": "Z1234567890ABC",
                            "records": [{"type": "ALIAS", "value": "d111111abcdef8.cloudfront.net", "ttl": 300}]
                        }
                        
                        mock_cf.return_value = {
                            "distribution_id": "E285K0Z0YGWJXZ",
                            "domain_name": "d111111abcdef8.cloudfront.net",
                            "aliases": ["demo.example.com"],
                            "origins": [{"id": "core-alb-origin", "domain_name": "core-alb-123.us-east-1.elb.amazonaws.com"}]
                        }
                        
                        mock_elb.return_value = {
                            "load_balancer_name": "core-alb",
                            "type": "application",
                            "target_groups": [{"target_group_name": "workload-tg", "targets": []}]
                        }
                        
                        # Mock agent executor
                        with patch('src.agent.agent_orchestrator.AgentExecutor') as mock_executor_class:
                            mock_executor = Mock()
                            mock_executor.invoke.return_value = {
                                "output": "Successfully traced demo.example.com through F5 WAF, Route53, CloudFront, and ALB",
                                "intermediate_steps": []
                            }
                            mock_executor_class.return_value = mock_executor
                            
                            # Create agent orchestrator
                            orchestrator = AgentOrchestrator(
                                credential_manager=mock_credential_manager,
                                llm=mock_llm,
                                max_iterations=10,
                                verbose=True
                            )
                            
                            # Execute query
                            result = orchestrator.execute_query(
                                query="Trace demo.example.com",
                                session_id="test-session",
                                request_id="test-request"
                            )
                            
                            # Verify result
                            assert result['success'] is True
                            assert 'demo.example.com' in result['output']
                            assert result['session_id'] == 'test-session'
                            assert 'intermediate_steps' in result

    def test_fqdn_trace_error_handling(self, mock_environment_variables):
        """Test error handling during FQDN tracing."""
        # Test with invalid FQDN
        with patch('src.lambda_handler.AgentOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.execute_query.return_value = {
                'success': False,
                'error': 'Invalid FQDN format: not-a-valid-fqdn',
                'output': '',
                'intermediate_steps': []
            }
            mock_orchestrator_class.return_value = mock_orchestrator
            
            with patch('src.lambda_handler.CredentialManager') as mock_cm_class:
                mock_cm_class.return_value = Mock()
                
                event = {
                    'httpMethod': 'POST',
                    'body': json.dumps({
                        'query': 'Trace not-a-valid-fqdn',
                        'session_id': 'test-session-error'
                    }),
                    'requestContext': {
                        'requestId': 'test-request-error',
                        'identity': {'sourceIp': '192.168.1.102'}
                    }
                }
                
                context = Mock()
                context.get_remaining_time_in_millis.return_value = 300000
                
                response = lambda_handler(event, context)
                
                # Verify error response
                assert response['statusCode'] == 200  # Lambda handler returns 200 even for agent errors
                
                body = json.loads(response['body'])
                assert body['status'] == 'error'
                assert 'Invalid FQDN format' in body['error_message']

    def test_fqdn_trace_timeout_handling(self, mock_environment_variables):
        """Test timeout handling during FQDN tracing."""
        with patch('src.lambda_handler.AgentOrchestrator') as mock_orchestrator_class:
            mock_orchestrator_class.side_effect = Exception("Timeout during agent execution")
            
            with patch('src.lambda_handler.CredentialManager') as mock_cm_class:
                mock_cm_class.return_value = Mock()
                
                event = {
                    'httpMethod': 'POST',
                    'body': json.dumps({
                        'query': 'Trace demo.example.com',
                        'session_id': 'test-session-timeout'
                    }),
                    'requestContext': {
                        'requestId': 'test-request-timeout',
                        'identity': {'sourceIp': '192.168.1.103'}
                    }
                }
                
                context = Mock()
                context.get_remaining_time_in_millis.return_value = 300000
                
                response = lambda_handler(event, context)
                
                # Verify timeout response
                assert response['statusCode'] == 500
                
                body = json.loads(response['body'])
                assert body['status'] == 'error'
                assert body['error_type'] == 'internal'

    def test_cross_account_access_in_fqdn_trace(self, mock_credential_manager):
        """Test cross-account access during FQDN tracing."""
        # Mock credential manager to track cross-account calls
        mock_credential_manager.get_boto3_client.return_value = Mock()
        
        with patch('src.agent.agent_orchestrator.create_bedrock_llm') as mock_llm_factory:
            mock_llm = Mock()
            mock_llm_factory.return_value = mock_llm
            
            with patch('src.tools.query_load_balancer') as mock_elb:
                # Mock ELB tool to simulate cross-account calls
                def mock_elb_call(dns_name=None, account_id=None, credential_manager=None):
                    if account_id == '111111111111':  # Core Network Account
                        return {
                            "load_balancer_name": "core-alb",
                            "account_id": "111111111111",
                            "target_groups": [{"target_group_name": "workload-tg"}]
                        }
                    elif account_id == '222222222222':  # Workload Account
                        return {
                            "load_balancer_name": "workload-alb",
                            "account_id": "222222222222",
                            "target_groups": [{"target_group_name": "backend-tg"}]
                        }
                    else:
                        return {"error": "Account not found"}
                
                mock_elb.side_effect = mock_elb_call
                
                with patch('src.agent.agent_orchestrator.AgentExecutor') as mock_executor_class:
                    mock_executor = Mock()
                    mock_executor.invoke.return_value = {
                        "output": "Traced across Core Network (111111111111) and Workload (222222222222) accounts",
                        "intermediate_steps": [
                            ('query_load_balancer', 'Queried Core Network Account'),
                            ('query_load_balancer', 'Queried Workload Account')
                        ]
                    }
                    mock_executor_class.return_value = mock_executor
                    
                    orchestrator = AgentOrchestrator(
                        credential_manager=mock_credential_manager,
                        llm=mock_llm
                    )
                    
                    result = orchestrator.execute_query(
                        query="Trace demo.example.com across all accounts",
                        request_id="test-cross-account"
                    )
                    
                    # Verify cross-account access was attempted
                    assert result['success'] is True
                    assert 'intermediate_steps' in result
                    assert len(result['intermediate_steps']) >= 2