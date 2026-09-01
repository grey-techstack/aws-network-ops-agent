"""
Example code showing how to retrieve and use F5 API credentials from AWS Secrets Manager
in the AWS Operations Agent Lambda function.
"""

import json
import boto3
import logging
from typing import Dict, Any
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class F5CredentialsManager:
    """Manages F5 API credentials from AWS Secrets Manager."""
    
    def __init__(self, secret_name: str, region_name: str = None):
        """
        Initialize the F5 credentials manager.
        
        Args:
            secret_name: Name of the secret in Secrets Manager
            region_name: AWS region (optional, uses default if not specified)
        """
        self.secret_name = secret_name
        self.secrets_client = boto3.client('secretsmanager', region_name=region_name)
        self._credentials_cache = None
    
    def get_credentials(self) -> Dict[str, str]:
        """
        Retrieve F5 API credentials from Secrets Manager.
        
        Returns:
            Dictionary containing F5 API credentials:
            {
                'api_url': 'https://tenant.console.ves.volterra.io/api',
                'api_token': 'your-api-token',
                'namespace': 'system'
            }
            
        Raises:
            ClientError: If secret cannot be retrieved
            ValueError: If secret format is invalid
        """
        if self._credentials_cache is not None:
            return self._credentials_cache
        
        try:
            logger.info(f"Retrieving F5 credentials from secret: {self.secret_name}")
            
            response = self.secrets_client.get_secret_value(SecretId=self.secret_name)
            secret_string = response['SecretString']
            
            # Parse JSON credentials
            credentials = json.loads(secret_string)
            
            # Validate required fields
            required_fields = ['api_url', 'api_token', 'namespace']
            for field in required_fields:
                if field not in credentials:
                    raise ValueError(f"Missing required field in F5 credentials: {field}")
            
            # Cache credentials for this execution
            self._credentials_cache = credentials
            
            logger.info("F5 credentials retrieved successfully")
            return credentials
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Secret not found: {self.secret_name}")
                raise ValueError(f"F5 credentials secret not found: {self.secret_name}")
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to secret: {self.secret_name}")
                raise ValueError(f"Access denied to F5 credentials secret: {self.secret_name}")
            else:
                logger.error(f"Error retrieving F5 credentials: {e}")
                raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in F5 credentials secret: {e}")
            raise ValueError(f"Invalid JSON format in F5 credentials secret: {e}")
    
    def get_api_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for F5 API requests.
        
        Returns:
            Dictionary containing HTTP headers for F5 API calls
        """
        credentials = self.get_credentials()
        
        return {
            'Authorization': f'APIToken {credentials["api_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def get_api_url(self, endpoint: str = '') -> str:
        """
        Get full F5 API URL for a specific endpoint.
        
        Args:
            endpoint: API endpoint path (optional)
            
        Returns:
            Full API URL
        """
        credentials = self.get_credentials()
        base_url = credentials['api_url'].rstrip('/')
        
        if endpoint:
            endpoint = endpoint.lstrip('/')
            return f"{base_url}/{endpoint}"
        
        return base_url
    
    def get_namespace(self) -> str:
        """
        Get F5 namespace.
        
        Returns:
            F5 namespace string
        """
        credentials = self.get_credentials()
        return credentials['namespace']


def example_f5_api_call():
    """
    Example function showing how to use F5 credentials to make an API call.
    """
    import requests
    import os
    
    # Get secret name from environment variable
    secret_name = os.environ.get('F5_SECRET_NAME', 'f5-distributed-cloud-api-credentials')
    
    try:
        # Initialize credentials manager
        f5_creds = F5CredentialsManager(secret_name)
        
        # Get credentials and headers
        headers = f5_creds.get_api_headers()
        namespace = f5_creds.get_namespace()
        
        # Example: List HTTP load balancers
        endpoint = f"config/namespaces/{namespace}/http_loadbalancers"
        url = f5_creds.get_api_url(endpoint)
        
        logger.info(f"Making F5 API call to: {url}")
        
        # Make API request
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        
        logger.info(f"F5 API call successful, received {len(data.get('items', []))} load balancers")
        
        return {
            'success': True,
            'data': data,
            'status_code': response.status_code
        }
        
    except Exception as e:
        logger.error(f"F5 API call failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Example Lambda handler showing F5 credentials usage.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Lambda response
    """
    try:
        # Test F5 API connection
        result = example_f5_api_call()
        
        if result['success']:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'F5 API connection successful',
                    'load_balancer_count': len(result['data'].get('items', []))
                })
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'F5 API connection failed',
                    'details': result['error']
                })
            }
            
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }


# Example usage in AWS Operations Agent tools
class F5WAFTool:
    """Example LangChain tool using F5 credentials."""
    
    def __init__(self, secret_name: str):
        self.f5_creds = F5CredentialsManager(secret_name)
    
    def query_load_balancer(self, fqdn: str) -> Dict[str, Any]:
        """
        Query F5 load balancer configuration for an FQDN.
        
        Args:
            fqdn: Fully qualified domain name
            
        Returns:
            Load balancer configuration
        """
        try:
            headers = self.f5_creds.get_api_headers()
            namespace = self.f5_creds.get_namespace()
            
            # Search for load balancer by domain
            endpoint = f"config/namespaces/{namespace}/http_loadbalancers"
            url = self.f5_creds.get_api_url(endpoint)
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Find load balancer matching FQDN
            for lb in data.get('items', []):
                domains = lb.get('spec', {}).get('domains', [])
                if fqdn in domains:
                    return {
                        'found': True,
                        'load_balancer': lb,
                        'domains': domains
                    }
            
            return {
                'found': False,
                'message': f'No load balancer found for FQDN: {fqdn}'
            }
            
        except Exception as e:
            logger.error(f"Error querying F5 load balancer: {e}")
            return {
                'found': False,
                'error': str(e)
            }


if __name__ == "__main__":
    # Test the credentials manager
    import os
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Test with environment variable or default
    secret_name = os.environ.get('F5_SECRET_NAME', 'f5-distributed-cloud-api-credentials')
    
    print(f"Testing F5 credentials manager with secret: {secret_name}")
    
    try:
        creds_manager = F5CredentialsManager(secret_name)
        credentials = creds_manager.get_credentials()
        
        print("✅ Credentials retrieved successfully")
        print(f"API URL: {credentials['api_url']}")
        print(f"Namespace: {credentials['namespace']}")
        print("API Token: [HIDDEN]")
        
        # Test API headers
        headers = creds_manager.get_api_headers()
        print(f"Headers: {list(headers.keys())}")
        
    except Exception as e:
        print(f"❌ Error: {e}")