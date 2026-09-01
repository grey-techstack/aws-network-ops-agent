"""
Enhanced Lambda handler - Nova Pro with AWS tools (no LangChain).
Incrementally adding AWS operations capabilities.
"""

import json
import logging
import boto3
from typing import Any, Dict, Optional
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Model configuration
MODEL_ID = "apac.amazon.nova-pro-v1:0"
REGION = "ap-southeast-1"


def query_route53_records(fqdn: str) -> Dict[str, Any]:
    """Query Route53 DNS records for a given FQDN with cross-account support."""
    import os
    
    try:
        # Try current account first
        route53 = boto3.client('route53')
        
        # List hosted zones
        zones_response = route53.list_hosted_zones()
        zones = zones_response.get('HostedZones', [])
        
        # Find matching zone
        matching_zone = None
        for zone in zones:
            zone_name = zone['Name'].rstrip('.')
            if fqdn.endswith(zone_name):
                matching_zone = zone
                break
        
        # If not found in current account, try core network account
        if not matching_zone:
            core_network_account_id = os.environ.get('CORE_NETWORK_ACCOUNT_ID')
            global_reader_role = os.environ.get('SSO_ROLE_ARN', '').split('/')[-1]
            
            if core_network_account_id and global_reader_role:
                logger.info(f"Zone not found in current account, trying core network account: {core_network_account_id}")
                
                # Assume role in core network account
                sts = boto3.client('sts')
                assumed_role = sts.assume_role(
                    RoleArn=f'arn:aws:iam::{core_network_account_id}:role/{global_reader_role}',
                    RoleSessionName='route53-query-session'
                )
                
                # Create Route53 client with assumed credentials
                route53 = boto3.client(
                    'route53',
                    aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
                    aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
                    aws_session_token=assumed_role['Credentials']['SessionToken']
                )
                
                # List hosted zones in core network account
                zones_response = route53.list_hosted_zones()
                zones = zones_response.get('HostedZones', [])
                
                # Find matching zone
                for zone in zones:
                    zone_name = zone['Name'].rstrip('.')
                    if fqdn.endswith(zone_name):
                        matching_zone = zone
                        break
        
        if not matching_zone:
            return {
                'success': False,
                'error': f'No hosted zone found for {fqdn} in current account or core network account',
                'fqdn': fqdn
            }
        
        # Query records
        zone_id = matching_zone['Id'].split('/')[-1]
        records_response = route53.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordName=fqdn,
            StartRecordType='A',
            MaxItems='10'
        )
        
        # Filter records that match the FQDN
        matching_records = []
        for record in records_response.get('ResourceRecordSets', []):
            if record['Name'].rstrip('.') == fqdn.rstrip('.'):
                matching_records.append(record)
        
        return {
            'success': True,
            'fqdn': fqdn,
            'zone_name': matching_zone['Name'],
            'zone_id': zone_id,
            'records': matching_records,
            'account': 'core_network' if matching_zone else 'current'
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Route53 query failed: {error_code} - {error_message}")
        return {
            'success': False,
            'error': f"AWS API error: {error_code} - {error_message}",
            'fqdn': fqdn
        }
    except Exception as e:
        logger.error(f"Unexpected error in Route53 query: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'fqdn': fqdn
        }


def detect_query_intent(query: str) -> Dict[str, Any]:
    """Detect user intent and extract parameters from query."""
    query_lower = query.lower()
    
    # Check for tool listing request
    if any(keyword in query_lower for keyword in ['tools', 'capabilities', 'what can you do', 'help']):
        return {
            'intent': 'list_tools',
            'params': {}
        }
    
    # Try to extract FQDN from query first (look for domain patterns)
    words = query.split()
    detected_fqdn = None
    for word in words:
        # Look for domain-like patterns (must have at least one dot and reasonable length)
        cleaned_word = word.strip('.,;:!?()[]{}"\' ')
        if '.' in cleaned_word and len(cleaned_word) > 3 and ' ' not in cleaned_word:
            # Additional validation: check if it looks like a domain
            parts = cleaned_word.split('.')
            if len(parts) >= 2 and all(part.isalnum() or '-' in part for part in parts):
                detected_fqdn = cleaned_word
                break
    
    # If we found an FQDN, check if this is a DNS/Route53 query
    if detected_fqdn:
        # Keywords that suggest DNS/Route53 query
        dns_keywords = ['route53', 'dns', 'fqdn', 'domain', 'records', 'query', 'lookup', 
                       'information', 'details', 'what', 'show', 'check', 'find']
        
        # If query contains DNS-related keywords OR just asks about a domain, treat as Route53 query
        if any(keyword in query_lower for keyword in dns_keywords):
            return {
                'intent': 'query_route53',
                'params': {'fqdn': detected_fqdn}
            }
    
    # Explicit Route53/DNS query without clear FQDN
    if any(keyword in query_lower for keyword in ['route53', 'dns records', 'dns query']):
        return {
            'intent': 'query_route53',
            'params': {},
            'error': 'No FQDN detected in query'
        }
    
    # Default: use Nova Pro for general questions
    return {
        'intent': 'general_query',
        'params': {}
    }


def format_route53_response(result: Dict[str, Any]) -> str:
    """Format Route53 query results for display."""
    if not result.get('success'):
        return f"❌ Route53 Query Failed\n\nError: {result.get('error', 'Unknown error')}\nFQDN: {result.get('fqdn', 'N/A')}"
    
    output = f"✅ Route53 Query Results\n\n"
    output += f"FQDN: {result['fqdn']}\n"
    output += f"Hosted Zone: {result['zone_name']}\n"
    output += f"Zone ID: {result['zone_id']}\n\n"
    
    records = result.get('records', [])
    if not records:
        output += "No DNS records found for this FQDN.\n"
    else:
        output += f"DNS Records ({len(records)} found):\n\n"
        for i, record in enumerate(records, 1):
            output += f"{i}. Type: {record['Type']}\n"
            output += f"   Name: {record['Name']}\n"
            output += f"   TTL: {record.get('TTL', 'N/A')}\n"
            
            if 'ResourceRecords' in record:
                values = [rr['Value'] for rr in record['ResourceRecords']]
                output += f"   Values: {', '.join(values)}\n"
            elif 'AliasTarget' in record:
                alias = record['AliasTarget']
                output += f"   Alias Target: {alias.get('DNSName', 'N/A')}\n"
                output += f"   Hosted Zone ID: {alias.get('HostedZoneId', 'N/A')}\n"
            
            output += "\n"
    
    return output


def get_tools_description() -> str:
    """Return description of available tools."""
    return """🛠️ Available AWS Tools

I can help you with the following AWS operations:

1. **Route53 DNS Query**
   - Query DNS records for any FQDN
   - Example: "Query DNS for demo.example.com"
   - Example: "What are the Route53 records for api.example.com?"

2. **CloudFront Distribution** (Coming soon)
   - Query CloudFront distribution details
   - Example: "Show CloudFront distribution for example.com"

3. **Load Balancer Query** (Coming soon)
   - Query ALB/NLB details and health status
   - Example: "Check load balancer health for my-alb.amazonaws.com"

4. **F5 Distributed Cloud** (Coming soon)
   - Query F5 load balancers and virtual hosts
   - Example: "Show F5 load balancers in namespace acme-net"

5. **VPC Flow Logs** (Coming soon)
   - Query VPC flow logs via Athena
   - Example: "Show flow logs for IP 10.0.1.5"

6. **CloudFront Logs** (Coming soon)
   - Query CloudFront access logs
   - Example: "Show CloudFront logs for the last hour"

**Current Status:**
- Model: Amazon Nova Pro (apac.amazon.nova-pro-v1:0)
- Region: ap-southeast-1
- Active Tools: Route53 DNS Query

For general AWS questions, just ask naturally and I'll use Nova Pro to help you!"""


def invoke_nova_pro(query: str) -> Dict[str, Any]:
    """Invoke Nova Pro model for general queries."""
    try:
        bedrock_client = boto3.client('bedrock-runtime', region_name=REGION)
        
        logger.info(f"Invoking Nova Pro model: {MODEL_ID}")
        response = bedrock_client.converse(
            modelId=MODEL_ID,
            messages=[
                {
                    "role": "user", 
                    "content": [{"text": query}]
                }
            ],
            inferenceConfig={
                "maxTokens": 2000, 
                "temperature": 0.1, 
                "topP": 0.9
            }
        )
        
        logger.info("Nova Pro response received successfully")
        
        return {
            'success': True,
            'output': response['output']['message']['content'][0]['text'],
            'usage': response.get('usage', {}),
            'stop_reason': response.get('stopReason', 'unknown')
        }
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Bedrock API error: {error_code} - {error_message}")
        return {
            'success': False,
            'error': f"Bedrock API error: {error_code} - {error_message}"
        }
    except Exception as e:
        logger.error(f"Unexpected error invoking Nova Pro: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Enhanced handler with Nova Pro and AWS tools."""
    logger.info("Enhanced handler started")
    
    try:
        # Parse request
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        query = body.get('query', 'Hello, can you help me?')
        logger.info(f"Processing query: {query}")
        
        # Detect intent
        intent_result = detect_query_intent(query)
        intent = intent_result['intent']
        params = intent_result.get('params', {})
        
        logger.info(f"Detected intent: {intent}")
        
        # Handle different intents
        if intent == 'list_tools':
            output = get_tools_description()
            response_type = 'tools_list'
            
        elif intent == 'query_route53':
            if 'error' in intent_result:
                output = f"⚠️ {intent_result['error']}\n\nPlease provide a specific FQDN to query.\nExample: 'Query DNS for demo.example.com'"
                response_type = 'error'
            else:
                fqdn = params['fqdn']
                logger.info(f"Querying Route53 for FQDN: {fqdn}")
                route53_result = query_route53_records(fqdn)
                output = format_route53_response(route53_result)
                response_type = 'route53_query'
                
        elif intent == 'general_query':
            logger.info("Using Nova Pro for general query")
            nova_result = invoke_nova_pro(query)
            if nova_result['success']:
                output = nova_result['output']
                response_type = 'nova_pro'
            else:
                output = f"Error invoking Nova Pro: {nova_result.get('error', 'Unknown error')}"
                response_type = 'error'
        else:
            output = "Unknown intent detected"
            response_type = 'error'
        
        # Format response
        result = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'output': output,
                'response_type': response_type,
                'intent': intent,
                'model_used': MODEL_ID if response_type == 'nova_pro' else 'aws_tools'
            })
        }
        
        logger.info(f"Request completed successfully - Response type: {response_type}")
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'error': str(e),
                'error_type': type(e).__name__
            })
        }
