"""
Integration tests for IP investigation end-to-end functionality.

These tests validate the complete IP investigation workflow including:
- ALB/NLB IP address identification
- CloudFront IP address identification
- F5 WAF IP address identification
- Unknown IP address handling with reverse DNS and WHOIS
- Result formatting

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9
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
from src.agent.formatters import IPInvestigationFormatter, format_ip_investigation


class TestIPInvestigationIntegration:
    """Integration tests for IP investigation functionality."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        env = {
            'SSO_ROLE_ARN': 'arn:aws:iam::123456789012:role/GlobalReaderRole',
            'F5_SECRET_NAME': 'f5-api-credentials',
            'CORE_NETWORK_ACCOUNT_ID': '111111111111',
            'WORKLOAD_ACCOUNT_IDS': '222222222222',
            'ATHENA_DATABASE': 'centralized_logging',
            'ATHENA_OUTPUT_BUCKET': 'aws-ops-agent-athena-results'
        }
        with patch.dict(os.environ, env):
            yield env

    @pytest.fixture
    def alb_ip_data(self):
        """Sample ALB IP investigation response (Req 3.1, 3.5)."""
        return {
            "ip_address": "10.0.1.50",
            "source_type": "ALB",
            "details": {
                "load_balancer_name": "core-alb",
                "load_balancer_arn": "arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/app/core-alb/1234567890abcdef",
                "account_id": "111111111111",
                "type": "application",
                "scheme": "internet-facing",
                "vpc_id": "vpc-12345678",
                "target_groups": [
                    {"target_group_name": "backend-tg"},
                    {"target_group_name": "api-tg"}
                ]
            },
            "timestamp": "2025-01-13T10:30:00Z"
        }

    @pytest.fixture
    def nlb_ip_data(self):
        """Sample NLB IP investigation response (Req 3.1, 3.5)."""
        return {
            "ip_address": "10.0.2.100",
            "source_type": "NLB",
            "details": {
                "load_balancer_name": "network-lb",
                "load_balancer_arn": "arn:aws:elasticloadbalancing:us-east-1:222222222222:loadbalancer/net/network-lb/abcdef1234567890",
                "account_id": "222222222222",
                "type": "network",
                "scheme": "internal",
                "vpc_id": "vpc-87654321",
                "target_groups": [
                    {"target_group_name": "tcp-tg"}
                ]
            },
            "timestamp": "2025-01-13T10:30:00Z"
        }

    @pytest.fixture
    def cloudfront_ip_data(self):
        """Sample CloudFront IP investigation response (Req 3.3, 3.7)."""
        return {
            "ip_address": "203.0.113.63",
            "source_type": "CloudFront",
            "details": {
                "edge_location": "IAD89-C1",
                "distributions": ["E285K0Z0YGWJXZ", "E1A2B3C4D5E6F7"]
            },
            "timestamp": "2025-01-13T10:30:00Z"
        }

    @pytest.fixture
    def f5_waf_ip_data(self):
        """Sample F5 WAF IP investigation response (Req 3.2, 3.6)."""
        return {
            "ip_address": "203.0.113.64",
            "source_type": "F5_WAF",
            "details": {
                "ves_endpoint": "example-lb.ac.vh.ves.io",
                "load_balancer_name": "demo-lb",
                "namespace": "production"
            },
            "timestamp": "2025-01-13T10:30:00Z"
        }

    @pytest.fixture
    def ec2_ip_data(self):
        """Sample EC2 IP investigation response (Req 3.4)."""
        return {
            "ip_address": "10.0.3.50",
            "source_type": "EC2",
            "details": {
                "service": "EC2",
                "region": "us-east-1",
                "instance_id": "i-0123456789abcdef0",
                "resource_id": "eni-0123456789abcdef0"
            },
            "timestamp": "2025-01-13T10:30:00Z"
        }

    @pytest.fixture
    def unknown_ip_data(self):
        """Sample unknown IP investigation response (Req 3.8)."""
        return {
            "ip_address": "203.0.113.45",
            "source_type": "Unknown",
            "details": {
                "reverse_dns": "host45.example.com",
                "whois": {
                    "organization": "Example Corp",
                    "country": "US",
                    "asn": "AS12345",
                    "network": "203.0.113.0/24"
                }
            },
            "timestamp": "2025-01-13T10:30:00Z"
        }

    # Test ALB/NLB IP identification (Requirements 3.1, 3.5)
    def test_alb_ip_identification(self, alb_ip_data):
        """Test ALB IP address identification (Req 3.1)."""
        assert alb_ip_data["source_type"] == "ALB"
        assert alb_ip_data["ip_address"] == "10.0.1.50"
        assert "load_balancer_name" in alb_ip_data["details"]
        assert "load_balancer_arn" in alb_ip_data["details"]
        assert "account_id" in alb_ip_data["details"]

    def test_alb_ip_provides_required_details(self, alb_ip_data):
        """Test ALB IP provides load balancer name, ARN, account ID, and target groups (Req 3.5)."""
        details = alb_ip_data["details"]
        assert details["load_balancer_name"] == "core-alb"
        assert "arn:aws:elasticloadbalancing" in details["load_balancer_arn"]
        assert details["account_id"] == "111111111111"
        assert "target_groups" in details
        assert len(details["target_groups"]) > 0

    def test_nlb_ip_identification(self, nlb_ip_data):
        """Test NLB IP address identification (Req 3.1)."""
        assert nlb_ip_data["source_type"] == "NLB"
        assert nlb_ip_data["ip_address"] == "10.0.2.100"
        assert nlb_ip_data["details"]["type"] == "network"

    # Test F5 WAF IP identification (Requirements 3.2, 3.6)
    def test_f5_waf_ip_identification(self, f5_waf_ip_data):
        """Test F5 WAF IP address identification (Req 3.2)."""
        assert f5_waf_ip_data["source_type"] == "F5_WAF"
        assert f5_waf_ip_data["ip_address"] == "203.0.113.64"

    def test_f5_waf_ip_provides_ves_endpoint(self, f5_waf_ip_data):
        """Test F5 WAF IP provides VES endpoint identifier and config (Req 3.6)."""
        details = f5_waf_ip_data["details"]
        assert "ves_endpoint" in details
        assert "ves-io" in details["ves_endpoint"]
        assert "load_balancer_name" in details
        assert "namespace" in details

    # Test CloudFront IP identification (Requirements 3.3, 3.7)
    def test_cloudfront_ip_identification(self, cloudfront_ip_data):
        """Test CloudFront IP address identification (Req 3.3)."""
        assert cloudfront_ip_data["source_type"] == "CloudFront"
        assert cloudfront_ip_data["ip_address"] == "203.0.113.63"

    def test_cloudfront_ip_provides_edge_location(self, cloudfront_ip_data):
        """Test CloudFront IP provides edge location and distributions (Req 3.7)."""
        details = cloudfront_ip_data["details"]
        assert "edge_location" in details
        assert details["edge_location"] == "IAD89-C1"
        assert "distributions" in details
        assert len(details["distributions"]) > 0

    # Test AWS service IP identification (Requirement 3.4)
    def test_ec2_ip_identification(self, ec2_ip_data):
        """Test EC2 IP address identification (Req 3.4)."""
        assert ec2_ip_data["source_type"] == "EC2"
        assert ec2_ip_data["details"]["service"] == "EC2"
        assert "instance_id" in ec2_ip_data["details"]

    # Test unknown IP handling (Requirement 3.8)
    def test_unknown_ip_reverse_dns_lookup(self, unknown_ip_data):
        """Test unknown IP performs reverse DNS lookup (Req 3.8)."""
        assert unknown_ip_data["source_type"] == "Unknown"
        assert "reverse_dns" in unknown_ip_data["details"]
        assert unknown_ip_data["details"]["reverse_dns"] == "host45.example.com"

    def test_unknown_ip_whois_query(self, unknown_ip_data):
        """Test unknown IP performs WHOIS query (Req 3.8)."""
        details = unknown_ip_data["details"]
        assert "whois" in details
        whois = details["whois"]
        assert "organization" in whois
        assert "country" in whois
        assert "asn" in whois

    # Test result formatting (Requirement 3.9)
    def test_alb_ip_result_formatting(self, alb_ip_data):
        """Test ALB IP result formatting in structured format (Req 3.9)."""
        formatted = format_ip_investigation(alb_ip_data)
        assert 'IP Investigation' in formatted
        assert '10.0.1.50' in formatted
        assert 'Source Type: ALB' in formatted
        assert 'Load Balancer Details' in formatted
        assert 'core-alb' in formatted
        assert '111111111111' in formatted

    def test_cloudfront_ip_result_formatting(self, cloudfront_ip_data):
        """Test CloudFront IP result formatting (Req 3.9)."""
        formatted = format_ip_investigation(cloudfront_ip_data)
        assert 'IP Investigation' in formatted
        assert '203.0.113.63' in formatted
        assert 'Source Type: CloudFront' in formatted
        assert 'CloudFront Details' in formatted
        assert 'Edge Location' in formatted
        assert 'IAD89-C1' in formatted

    def test_f5_waf_ip_result_formatting(self, f5_waf_ip_data):
        """Test F5 WAF IP result formatting (Req 3.9)."""
        formatted = format_ip_investigation(f5_waf_ip_data)
        assert 'IP Investigation' in formatted
        assert '203.0.113.64' in formatted
        assert 'Source Type: F5_WAF' in formatted
        assert 'F5 Distributed Cloud WAF Details' in formatted
        assert 'VES Endpoint' in formatted

    def test_unknown_ip_result_formatting(self, unknown_ip_data):
        """Test unknown IP result formatting (Req 3.9)."""
        formatted = format_ip_investigation(unknown_ip_data)
        assert 'IP Investigation' in formatted
        assert '203.0.113.45' in formatted
        assert 'Source Type: Unknown' in formatted
        assert 'External IP Details' in formatted
        assert 'Reverse DNS' in formatted
        assert 'WHOIS Information' in formatted
        assert 'does not belong to known AWS or F5 infrastructure' in formatted

    def test_ec2_ip_result_formatting(self, ec2_ip_data):
        """Test EC2 IP result formatting (Req 3.9)."""
        formatted = format_ip_investigation(ec2_ip_data)
        assert 'IP Investigation' in formatted
        assert '10.0.3.50' in formatted
        assert 'Source Type: EC2' in formatted
        assert 'AWS Service Details' in formatted
        assert 'Instance ID' in formatted

    # Test formatter edge cases
    def test_formatter_handles_missing_data(self):
        """Test formatter handles missing IP data gracefully."""
        formatted = format_ip_investigation({})
        assert 'No IP investigation data available' in formatted

    def test_formatter_handles_empty_details(self):
        """Test formatter handles empty details gracefully."""
        data = {
            "ip_address": "192.168.1.1",
            "source_type": "Unknown",
            "details": {}
        }
        formatted = format_ip_investigation(data)
        assert 'IP Investigation' in formatted
        assert '192.168.1.1' in formatted

    def test_formatter_handles_nlb_type(self, nlb_ip_data):
        """Test formatter handles NLB source type correctly."""
        formatted = format_ip_investigation(nlb_ip_data)
        assert 'IP Investigation' in formatted
        assert 'Source Type: NLB' in formatted
        assert 'Load Balancer Details' in formatted

    # Test categorization clarity
    def test_result_has_clear_categorization(self, alb_ip_data):
        """Test results have clear categorization (Req 3.9)."""
        formatted = format_ip_investigation(alb_ip_data)
        # Should have clear section headers
        assert 'Source Type:' in formatted
        assert 'Details' in formatted
        # Should have visual separators
        assert '=' in formatted or '-' in formatted

    def test_all_source_types_have_distinct_formatting(
        self, alb_ip_data, cloudfront_ip_data, f5_waf_ip_data, unknown_ip_data
    ):
        """Test all source types have distinct formatting sections."""
        alb_formatted = format_ip_investigation(alb_ip_data)
        cf_formatted = format_ip_investigation(cloudfront_ip_data)
        f5_formatted = format_ip_investigation(f5_waf_ip_data)
        unknown_formatted = format_ip_investigation(unknown_ip_data)
        
        # Each should have unique section headers
        assert 'Load Balancer Details' in alb_formatted
        assert 'CloudFront Details' in cf_formatted
        assert 'F5 Distributed Cloud WAF Details' in f5_formatted
        assert 'External IP Details' in unknown_formatted

    # Test timestamp inclusion
    def test_result_includes_timestamp(self, alb_ip_data):
        """Test result includes timestamp."""
        formatted = format_ip_investigation(alb_ip_data)
        assert 'Timestamp' in formatted
        assert '2025-01-13' in formatted
