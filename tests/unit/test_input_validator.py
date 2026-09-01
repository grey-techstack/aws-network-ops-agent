"""Unit tests for input validation functions."""

import pytest
from src.agent.input_validator import (
    validate_fqdn,
    validate_ip_address,
    validate_datetime_range,
    validate_date_range,
    validate_cloudfront_distribution_id,
    validate_http_status_code_range,
    validate_tool_input,
    ValidationError
)


class TestValidateFQDN:
    """Test suite for FQDN validation."""
    
    def test_valid_fqdn(self):
        """Test validation of valid FQDNs."""
        valid_fqdns = [
            "demo.example.com",
            "test.example.org",
            "sub.domain.example.com",
            "a.b.c.d.e.com",
            "test-123.example.com",
            "123.example.com"
        ]
        
        for fqdn in valid_fqdns:
            is_valid, error = validate_fqdn(fqdn)
            assert is_valid is True, f"Expected {fqdn} to be valid"
            assert error is None
    
    def test_fqdn_with_trailing_dot(self):
        """Test that FQDNs with trailing dots are accepted."""
        is_valid, error = validate_fqdn("demo.example.com.")
        assert is_valid is True
        assert error is None
    
    def test_empty_fqdn(self):
        """Test that empty FQDNs are rejected."""
        is_valid, error = validate_fqdn("")
        assert is_valid is False
        assert "non-empty" in error
    
    def test_single_label_fqdn(self):
        """Test that single-label FQDNs are rejected."""
        is_valid, error = validate_fqdn("localhost")
        assert is_valid is False
        assert "at least two labels" in error
    
    def test_fqdn_too_long(self):
        """Test that FQDNs exceeding 253 characters are rejected."""
        long_fqdn = "a" * 250 + ".com"
        is_valid, error = validate_fqdn(long_fqdn)
        assert is_valid is False
        assert "maximum length" in error
    
    def test_label_too_long(self):
        """Test that labels exceeding 63 characters are rejected."""
        long_label = "a" * 64 + ".example.com"
        is_valid, error = validate_fqdn(long_label)
        assert is_valid is False
        assert "63 characters" in error
    
    def test_invalid_characters(self):
        """Test that FQDNs with invalid characters are rejected."""
        invalid_fqdns = [
            "demo_test.com",
            "demo@test.com",
            "demo test.com",
            "demo!.com"
        ]
        
        for fqdn in invalid_fqdns:
            is_valid, error = validate_fqdn(fqdn)
            assert is_valid is False
    
    def test_label_starting_with_hyphen(self):
        """Test that labels starting with hyphens are rejected."""
        is_valid, error = validate_fqdn("-demo.example.com")
        assert is_valid is False
    
    def test_label_ending_with_hyphen(self):
        """Test that labels ending with hyphens are rejected."""
        is_valid, error = validate_fqdn("demo-.example.com")
        assert is_valid is False


class TestValidateIPAddress:
    """Test suite for IP address validation."""
    
    def test_valid_ip_addresses(self):
        """Test validation of valid IP addresses."""
        valid_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "0.0.0.0",
            "255.255.255.255"
        ]
        
        for ip in valid_ips:
            is_valid, error = validate_ip_address(ip)
            assert is_valid is True, f"Expected {ip} to be valid"
            assert error is None
    
    def test_empty_ip(self):
        """Test that empty IP addresses are rejected."""
        is_valid, error = validate_ip_address("")
        assert is_valid is False
        assert "non-empty" in error
    
    def test_invalid_ip_format(self):
        """Test that invalid IP formats are rejected."""
        invalid_ips = [
            "192.168.1",
            "192.168.1.1.1",
            "192.168.1.a",
            "192.168..1",
            "192.168.1.1.1",
            "not-an-ip"
        ]
        
        for ip in invalid_ips:
            is_valid, error = validate_ip_address(ip)
            assert is_valid is False
    
    def test_octet_exceeds_255(self):
        """Test that octets exceeding 255 are rejected."""
        is_valid, error = validate_ip_address("192.168.1.256")
        assert is_valid is False
        assert "255" in error


class TestValidateDatetimeRange:
    """Test suite for datetime range validation."""
    
    def test_valid_datetime_range(self):
        """Test validation of valid datetime ranges."""
        is_valid, error = validate_datetime_range(
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z"
        )
        assert is_valid is True
        assert error is None
    
    def test_none_values(self):
        """Test that None values are accepted."""
        is_valid, error = validate_datetime_range(None, None)
        assert is_valid is True
        assert error is None
    
    def test_invalid_start_time_format(self):
        """Test that invalid start_time format is rejected."""
        is_valid, error = validate_datetime_range(
            "invalid-date",
            "2024-01-02T00:00:00Z"
        )
        assert is_valid is False
        assert "start_time" in error
    
    def test_invalid_end_time_format(self):
        """Test that invalid end_time format is rejected."""
        is_valid, error = validate_datetime_range(
            "2024-01-01T00:00:00Z",
            "invalid-date"
        )
        assert is_valid is False
        assert "end_time" in error
    
    def test_start_after_end(self):
        """Test that start_time after end_time is rejected."""
        is_valid, error = validate_datetime_range(
            "2024-01-02T00:00:00Z",
            "2024-01-01T00:00:00Z"
        )
        assert is_valid is False
        assert "before" in error


class TestValidateDateRange:
    """Test suite for date range validation."""
    
    def test_valid_date_range(self):
        """Test validation of valid date ranges."""
        is_valid, error = validate_date_range("2024-01-01", "2024-01-31")
        assert is_valid is True
        assert error is None
    
    def test_same_date(self):
        """Test that same start and end dates are accepted."""
        is_valid, error = validate_date_range("2024-01-01", "2024-01-01")
        assert is_valid is True
        assert error is None
    
    def test_none_values(self):
        """Test that None values are accepted."""
        is_valid, error = validate_date_range(None, None)
        assert is_valid is True
        assert error is None
    
    def test_invalid_date_format(self):
        """Test that invalid date formats are rejected."""
        invalid_dates = [
            ("01-01-2024", "2024-01-31"),
            ("2024/01/01", "2024-01-31"),
            ("2024-1-1", "2024-01-31")
        ]
        
        for start, end in invalid_dates:
            is_valid, error = validate_date_range(start, end)
            assert is_valid is False
    
    def test_invalid_date_values(self):
        """Test that invalid date values are rejected."""
        is_valid, error = validate_date_range("2024-13-01", "2024-12-31")
        assert is_valid is False
    
    def test_start_after_end(self):
        """Test that start_date after end_date is rejected."""
        is_valid, error = validate_date_range("2024-12-31", "2024-01-01")
        assert is_valid is False
        assert "before" in error


class TestValidateCloudfrontDistributionID:
    """Test suite for CloudFront distribution ID validation."""
    
    def test_valid_distribution_id(self):
        """Test validation of valid distribution IDs."""
        valid_ids = [
            "E285K0Z0YGWJXZ",
            "ABCDEFGHIJKLMN",
            "1234567890ABCD"
        ]
        
        for dist_id in valid_ids:
            is_valid, error = validate_cloudfront_distribution_id(dist_id)
            assert is_valid is True, f"Expected {dist_id} to be valid"
            assert error is None
    
    def test_empty_distribution_id(self):
        """Test that empty distribution IDs are rejected."""
        is_valid, error = validate_cloudfront_distribution_id("")
        assert is_valid is False
        assert "non-empty" in error
    
    def test_wrong_length(self):
        """Test that distribution IDs with wrong length are rejected."""
        is_valid, error = validate_cloudfront_distribution_id("E285K0Z")
        assert is_valid is False
        assert "14 characters" in error
    
    def test_lowercase_characters(self):
        """Test that lowercase characters are rejected."""
        is_valid, error = validate_cloudfront_distribution_id("e285k0z0ygwjxz")
        assert is_valid is False
        assert "uppercase" in error
    
    def test_special_characters(self):
        """Test that special characters are rejected."""
        is_valid, error = validate_cloudfront_distribution_id("E285K0Z0YGWJ-Z")
        assert is_valid is False


class TestValidateHTTPStatusCodeRange:
    """Test suite for HTTP status code range validation."""
    
    def test_valid_status_code_range(self):
        """Test validation of valid status code ranges."""
        is_valid, error = validate_http_status_code_range(200, 299)
        assert is_valid is True
        assert error is None
    
    def test_none_values(self):
        """Test that None values are accepted."""
        is_valid, error = validate_http_status_code_range(None, None)
        assert is_valid is True
        assert error is None
    
    def test_min_code_below_100(self):
        """Test that status codes below 100 are rejected."""
        is_valid, error = validate_http_status_code_range(99, 200)
        assert is_valid is False
        assert "100 and 599" in error
    
    def test_max_code_above_599(self):
        """Test that status codes above 599 are rejected."""
        is_valid, error = validate_http_status_code_range(200, 600)
        assert is_valid is False
        assert "100 and 599" in error
    
    def test_min_greater_than_max(self):
        """Test that min > max is rejected."""
        is_valid, error = validate_http_status_code_range(500, 400)
        assert is_valid is False
        assert "less than or equal" in error


class TestValidateToolInput:
    """Test suite for tool input validation."""
    
    def test_route53_tool_valid_input(self):
        """Test validation of valid Route53 tool input."""
        validate_tool_input("route53", fqdn="demo.example.com")
        # Should not raise exception
    
    def test_route53_tool_invalid_fqdn(self):
        """Test validation of invalid Route53 tool input."""
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_input("route53", fqdn="invalid_fqdn")
        assert "Invalid FQDN" in str(exc_info.value)
    
    def test_cloudfront_tool_valid_input(self):
        """Test validation of valid CloudFront tool input."""
        validate_tool_input("cloudfront", distribution_id="E285K0Z0YGWJXZ")
        # Should not raise exception
    
    def test_cloudfront_tool_invalid_distribution_id(self):
        """Test validation of invalid CloudFront tool input."""
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_input("cloudfront", distribution_id="INVALID")
        assert "Invalid distribution ID" in str(exc_info.value)
    
    def test_athena_vpc_flow_logs_valid_input(self):
        """Test validation of valid Athena VPC flow logs input."""
        validate_tool_input(
            "athena_vpc_flow_logs",
            source_ip="10.0.1.100",
            destination_ip="10.0.2.200",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-02T00:00:00Z"
        )
        # Should not raise exception
    
    def test_athena_vpc_flow_logs_invalid_ip(self):
        """Test validation of invalid Athena VPC flow logs input."""
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_input(
                "athena_vpc_flow_logs",
                source_ip="invalid-ip"
            )
        assert "Invalid source IP" in str(exc_info.value)
    
    def test_athena_cloudfront_logs_valid_input(self):
        """Test validation of valid Athena CloudFront logs input."""
        validate_tool_input(
            "athena_cloudfront_logs",
            distribution_id="E285K0Z0YGWJXZ",
            start_date="2024-01-01",
            end_date="2024-01-31",
            status_code_min=400,
            status_code_max=599
        )
        # Should not raise exception
    
    def test_athena_cloudfront_logs_invalid_date_range(self):
        """Test validation of invalid Athena CloudFront logs input."""
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_input(
                "athena_cloudfront_logs",
                distribution_id="E285K0Z0YGWJXZ",
                start_date="2024-12-31",
                end_date="2024-01-01"
            )
        assert "Invalid date range" in str(exc_info.value)
    
    def test_ip_lookup_tool_valid_input(self):
        """Test validation of valid IP lookup tool input."""
        validate_tool_input("ip_lookup", ip_address="203.0.113.63")
        # Should not raise exception
    
    def test_ip_lookup_tool_invalid_ip(self):
        """Test validation of invalid IP lookup tool input."""
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_input("ip_lookup", ip_address="999.999.999.999")
        assert "Invalid IP address" in str(exc_info.value)
