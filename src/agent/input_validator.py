"""Input validation functions for tool parameters."""

import re
from datetime import datetime
from typing import Optional, Tuple


class ValidationError(Exception):
    """Exception raised when input validation fails."""
    pass


def validate_fqdn(fqdn: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a Fully Qualified Domain Name (FQDN).
    
    Args:
        fqdn: The FQDN to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not fqdn or not isinstance(fqdn, str):
        return False, "FQDN must be a non-empty string"
    
    # Remove trailing dot if present
    fqdn = fqdn.rstrip('.')
    
    # Check length
    if len(fqdn) > 253:
        return False, "FQDN exceeds maximum length of 253 characters"
    
    # FQDN pattern: labels separated by dots
    # Each label: 1-63 chars, alphanumeric and hyphens, cannot start/end with hyphen
    label_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    labels = fqdn.split('.')
    
    if len(labels) < 2:
        return False, "FQDN must have at least two labels (e.g., example.com)"
    
    for label in labels:
        if not label:
            return False, "FQDN contains empty label"
        
        if len(label) > 63:
            return False, f"Label '{label}' exceeds maximum length of 63 characters"
        
        if not re.match(label_pattern, label):
            return False, f"Label '{label}' contains invalid characters or format"
    
    return True, None


def validate_ip_address(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an IPv4 address.
    
    Args:
        ip: The IP address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not ip or not isinstance(ip, str):
        return False, "IP address must be a non-empty string"
    
    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(ipv4_pattern, ip)
    
    if not match:
        return False, "IP address must be in IPv4 format (e.g., 192.168.1.1)"
    
    # Validate each octet is 0-255
    octets = [int(match.group(i)) for i in range(1, 5)]
    for octet in octets:
        if octet > 255:
            return False, f"IP address octet {octet} exceeds maximum value of 255"
    
    return True, None


def validate_datetime_range(
    start_time: Optional[str],
    end_time: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate a date/time range.
    
    Args:
        start_time: Start time in ISO format (optional)
        end_time: End time in ISO format (optional)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if start_time is None and end_time is None:
        return True, None
    
    # Validate start_time format
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return False, f"Invalid start_time format: {start_time}. Expected ISO format (e.g., 2024-01-01T00:00:00Z)"
    
    # Validate end_time format
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return False, f"Invalid end_time format: {end_time}. Expected ISO format (e.g., 2024-01-01T00:00:00Z)"
    
    # Validate that start_time is before end_time
    if start_time and end_time:
        if start_dt >= end_dt:
            return False, "start_time must be before end_time"
    
    return True, None


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate a date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if start_date is None and end_date is None:
        return True, None
    
    # Date pattern: YYYY-MM-DD
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    
    # Validate start_date format
    if start_date:
        if not re.match(date_pattern, start_date):
            return False, f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD"
        
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            return False, f"Invalid start_date: {start_date}"
    
    # Validate end_date format
    if end_date:
        if not re.match(date_pattern, end_date):
            return False, f"Invalid end_date format: {end_date}. Expected YYYY-MM-DD"
        
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return False, f"Invalid end_date: {end_date}"
    
    # Validate that start_date is before or equal to end_date
    if start_date and end_date:
        if start_dt > end_dt:
            return False, "start_date must be before or equal to end_date"
    
    return True, None


def validate_cloudfront_distribution_id(distribution_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a CloudFront distribution ID.
    
    Args:
        distribution_id: The distribution ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not distribution_id or not isinstance(distribution_id, str):
        return False, "Distribution ID must be a non-empty string"
    
    # CloudFront distribution IDs are typically 14 characters, alphanumeric
    # Example: E285K0Z0YGWJXZ
    if len(distribution_id) != 14:
        return False, f"Distribution ID must be 14 characters long (got {len(distribution_id)})"
    
    if not re.match(r'^[A-Z0-9]+$', distribution_id):
        return False, "Distribution ID must contain only uppercase letters and numbers"
    
    return True, None


def validate_http_status_code_range(
    min_code: Optional[int],
    max_code: Optional[int]
) -> Tuple[bool, Optional[str]]:
    """
    Validate HTTP status code range.
    
    Args:
        min_code: Minimum status code (optional)
        max_code: Maximum status code (optional)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if min_code is None and max_code is None:
        return True, None
    
    # Validate min_code
    if min_code is not None:
        if not isinstance(min_code, int):
            return False, "Minimum status code must be an integer"
        
        if min_code < 100 or min_code > 599:
            return False, f"Minimum status code must be between 100 and 599 (got {min_code})"
    
    # Validate max_code
    if max_code is not None:
        if not isinstance(max_code, int):
            return False, "Maximum status code must be an integer"
        
        if max_code < 100 or max_code > 599:
            return False, f"Maximum status code must be between 100 and 599 (got {max_code})"
    
    # Validate range
    if min_code is not None and max_code is not None:
        if min_code > max_code:
            return False, f"Minimum status code ({min_code}) must be less than or equal to maximum ({max_code})"
    
    return True, None


def validate_tool_input(tool_name: str, **parameters) -> None:
    """
    Validate tool input parameters based on tool name.
    
    Args:
        tool_name: Name of the tool
        **parameters: Tool parameters to validate
        
    Raises:
        ValidationError: If validation fails
    """
    if tool_name == "route53":
        if "fqdn" in parameters:
            is_valid, error = validate_fqdn(parameters["fqdn"])
            if not is_valid:
                raise ValidationError(f"Invalid FQDN: {error}")
    
    elif tool_name == "cloudfront":
        if "domain_name" in parameters:
            is_valid, error = validate_fqdn(parameters["domain_name"])
            if not is_valid:
                raise ValidationError(f"Invalid domain name: {error}")
        
        if "distribution_id" in parameters:
            is_valid, error = validate_cloudfront_distribution_id(parameters["distribution_id"])
            if not is_valid:
                raise ValidationError(f"Invalid distribution ID: {error}")
    
    elif tool_name == "elb":
        if "dns_name" in parameters:
            is_valid, error = validate_fqdn(parameters["dns_name"])
            if not is_valid:
                raise ValidationError(f"Invalid DNS name: {error}")
    
    elif tool_name == "athena_vpc_flow_logs":
        if "source_ip" in parameters and parameters["source_ip"]:
            is_valid, error = validate_ip_address(parameters["source_ip"])
            if not is_valid:
                raise ValidationError(f"Invalid source IP: {error}")
        
        if "destination_ip" in parameters and parameters["destination_ip"]:
            is_valid, error = validate_ip_address(parameters["destination_ip"])
            if not is_valid:
                raise ValidationError(f"Invalid destination IP: {error}")
        
        is_valid, error = validate_datetime_range(
            parameters.get("start_time"),
            parameters.get("end_time")
        )
        if not is_valid:
            raise ValidationError(f"Invalid time range: {error}")
    
    elif tool_name == "athena_cloudfront_logs":
        if "distribution_id" in parameters:
            is_valid, error = validate_cloudfront_distribution_id(parameters["distribution_id"])
            if not is_valid:
                raise ValidationError(f"Invalid distribution ID: {error}")
        
        is_valid, error = validate_date_range(
            parameters.get("start_date"),
            parameters.get("end_date")
        )
        if not is_valid:
            raise ValidationError(f"Invalid date range: {error}")
        
        is_valid, error = validate_http_status_code_range(
            parameters.get("status_code_min"),
            parameters.get("status_code_max")
        )
        if not is_valid:
            raise ValidationError(f"Invalid status code range: {error}")
    
    elif tool_name == "f5_waf":
        if "fqdn" in parameters:
            is_valid, error = validate_fqdn(parameters["fqdn"])
            if not is_valid:
                raise ValidationError(f"Invalid FQDN: {error}")
    
    elif tool_name == "ip_lookup":
        if "ip_address" in parameters:
            is_valid, error = validate_ip_address(parameters["ip_address"])
            if not is_valid:
                raise ValidationError(f"Invalid IP address: {error}")
