"""
Intermediate Lambda handler - Nova Pro with basic AWS tools (no LangChain agent).
"""

import json
import logging
import boto3
from typing import Any, Dict
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Model configuration
MODEL_ID = "apac.amazon.nova-pro-v1:0"
REGION = "ap-southeast-1"


def query_route53_basic(fqdn: str) -> Dict[str, Any]:
    """Basic Route53 query without credential manager."""
    try:
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
        
        if not matching_zone:
            return {'error': f'No hosted zone found for {fqdn}'}
        
        # Query records
        zone_id = matching_zone['Id'].split('/')[-1]
        records_response = route53.list_resource_record_sets(
            HostedZoneId=zone_id,
            StartRecordName=fqdn,
            StartRecordType='A',
            MaxItems='10'
        )
        
        return {
            'zone': matching_zone['Name'],
            'zone_id': zone_id,
            'records': records_response.get('ResourceRecordSets', [])[:5]
        }
    except Exception as e:
        logger.error(f"Route53 query failed: {str(e)}")
        return {'error': str(e)}


def process_query_with_tools(query: str) -> str:
    """Process query and determine if tools are needed."""
    query_lower = query.lower()
    
    # Check if query is about available tools
    if 'tools' in query_lower or 'capabilities' in query_lower or 'what can you do' in query_lower:
        return """I have access to the following AWS tools:

1. **Route53 DNS Query**: Query DNS records for any FQDN
   - Example: "Query DNS for demo.example.com"
   
2. **CloudFront Distribution**: Query CloudFront distribution details
   - Example: "Show CloudFront distribution for example.com"
   
3. **Load Balancer Query**: Query ALB/NLB details and health status
   - Example: "Check load balancer health for my-alb.amazonaws.com"
   
4. **F5 Distributed Cloud**: Query F5 load balancers and virtual hosts
   - Example: "Show F5 load balancers in namespace acme-net"

5. **VPC Flow Logs**: Query VPC flow logs via Athena
   - Example: "Show flow logs for IP 10.0.1.5"

6. **CloudFront Logs**: Query CloudFront access logs
   - Example: "Show CloudFront logs for the last hour"

Currently running with Amazon Nova Pro model in ap-southeast-1 region."""
    
    # Check if query is about Route53/DNS
    if 'route53' in query_lower or 'dns' in query_lower or 'fqdn' in query_lower:
        # Try to extract FQDN from query
        words = query.split()
        for word in words:
            if '.' in word and len(word) > 3:
                # Likely an FQDN
                fqdn = word.strip('.,;:!?')
                logger.info(f"Detected FQDN: {fqdn}")
                result = query_route53_basic(fqdn)
                return f"Route53 Query Results for {fqdn}:\n{json.dumps(result, indent=2)}"
        
        return "Please provide a specific FQDN to query. Example: 'Query DNS for demo.example.com'"
    
    # For other queries, use Nova Pro to respond
    return None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Intermediate handler with Nova Pro and basic AWS tools."""
    logger.info("Intermediate handler started")
    
    try:
        # Parse request
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        query = body.get('query', 'Hello, can you help me?')
        logger.info(f"Processing query: {query}")
        
        # Check if we can handle with tools
        tool_response = process_query_with_tools(query)
        
        if tool_response:
            # Return tool response directly
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'success',
                    'output': tool_response,
                    'message': 'Tool-based response',
                    'model_used': 'tools'
                })
            }
        
        # Otherwise, use Nova Pro
        logger.info(f"Creating Bedrock client for region: {REGION}")
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
        
        # Extract response content
        analysis_result = response['output']['message']['content'][0]['text']
        
        # Format response
        result = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'success',
                'output': analysis_result,
                'message': 'Nova Pro response',
                'model_used': MODEL_ID,
                'usage': response.get('usage', {}),
                'stop_reason': response.get('stopReason', 'unknown')
            })
        }
        
        logger.info("Request completed successfully")
        return result
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"AWS API error: {error_code} - {error_message}")
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'error',
                'error': f"AWS API error: {error_code} - {error_message}",
                'error_type': 'aws_api_error'
            })
        }
        
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
