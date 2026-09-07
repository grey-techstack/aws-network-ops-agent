# AWS Operations Agent Tools

This directory contains LangChain tools for querying various AWS services.

## Implemented Tools

### 1. Route53 Tool (`route53_tool.py`)
- **Purpose**: Query Route53 DNS records for FQDNs
- **Key Features**:
  - Find hosted zones by FQDN
  - Retrieve DNS records (A, AAAA, CNAME, TXT, MX, NS, ALIAS)
  - Handle ALIAS records with target information
  - Graceful error handling for missing zones

### 1a. Route53 Hosted Zones (`route53_tool.py`)
- **Purpose**: List Route53 hosted zones in a given account
- **Key Features**:
  - Optional `account_id` input (defaults to `CORE_NETWORK_ACCOUNT_ID`)
  - Returns zone id, name, private flag, and record counts
  - Uses credential manager for cross-account access

### 2. CloudFront Tool (`cloudfront_tool.py`)
- **Purpose**: Query CloudFront distributions and origins
- **Key Features**:
  - Lookup by distribution ID or domain name
  - Retrieve origin configurations
  - Support for aliases and custom origins
  - Extract protocol policies and connection settings

### 3. ELB Tool (`elb_tool.py`)
- **Purpose**: Query ALB/NLB load balancers
- **Key Features**:
  - Lookup by DNS name
  - Cross-account access support
  - Retrieve target groups and health status
  - Support for both Application and Network load balancers

## Usage Example

```python
from src.credentials.credential_manager import CredentialManager
from src.tools import (
    Route53Tool,
    CloudFrontTool,
    ELBTool,
)

# Initialize credential manager
credential_manager = CredentialManager(sso_role_arn="arn:aws:iam::123456789012:role/GlobalReader")

# Initialize tools
route53_tool = Route53Tool(credential_manager)
cloudfront_tool = CloudFrontTool(credential_manager)
elb_tool = ELBTool(credential_manager)

# Query Route53
dns_records = route53_tool.query_records("demo.example.com")

# Query CloudFront
distribution = cloudfront_tool.query_distribution(domain_name="demo.example.com")

# Query Load Balancer
lb_info = elb_tool.query_load_balancer(dns_name="my-alb-123.us-east-1.elb.amazonaws.com")

# Query VPC Flow Logs
flow_logs = vpc_flow_logs_tool.query_flow_logs(
    source_ip="10.0.1.100",
    destination_ip="10.0.2.200"
)

# Query CloudFront Logs
cf_logs = cloudfront_logs_tool.query_logs(
    distribution_id="E285K0Z0YGWJXZ",
    start_date="2025-01-01",
    end_date="2025-01-07",
    status_code_min=400,
    status_code_max=599
)
```

## Error Handling

All tools implement comprehensive error handling:
- AWS API errors (throttling, permissions, not found)
- Network errors
- Invalid input errors

Errors are returned in the result dictionary with an "error" field containing a descriptive message.

## Requirements Validation

These tools satisfy the following requirements from the design document:

- **Requirement 1.3**: Route53 DNS record querying
- **Requirement 1.4**: CloudFront distribution querying
- **Requirements 1.5-1.8**: ALB/NLB querying with cross-account support
- **Requirements 2.2-2.6**: CloudFront logs querying with all required fields

## Next Steps

The following components still need to be implemented:
- F5 WAF Tool (for F5 Distributed Cloud API)
- IP Lookup Tool (for IP address investigation)
- Tool orchestration and caching
- LangChain agent integration
- Lambda handler
- API Gateway interface
