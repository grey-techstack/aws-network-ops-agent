"""Teams Outgoing Webhook handler for AWS Lambda.

This handler processes Teams Outgoing Webhook requests and responds asynchronously
to avoid the 5-second timeout limitation.

Flow:
1. Teams sends message to Lambda via Outgoing Webhook
2. Lambda immediately returns "Processing..." message (< 5 seconds)
3. Lambda processes query in background
4. Lambda sends final result back to Teams via Incoming Webhook
"""

import json
import logging
import os
from typing import Any, Dict, Optional
from datetime import datetime
import requests
import boto3

from src.agent.agent_orchestrator import AgentOrchestrator, AgentOrchestratorError
from src.credentials.credential_manager import CredentialManager

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variables for Lambda container reuse
_agent_orchestrator: Optional[AgentOrchestrator] = None
_credential_manager: Optional[CredentialManager] = None


def get_environment_variables() -> Dict[str, str]:
    """Get and validate required environment variables."""
    required_vars = {
        'CROSS_ACCOUNT_ROLE_NAME': os.environ.get('CROSS_ACCOUNT_ROLE_NAME', 'aws-ops-agent-cross-account-role'),
        'F5_SECRET_NAME': os.environ.get('F5_SECRET_NAME'),
        'CORE_NETWORK_ACCOUNT_ID': os.environ.get('CORE_NETWORK_ACCOUNT_ID'),
        'WORKLOAD_ACCOUNT_IDS': os.environ.get('WORKLOAD_ACCOUNT_IDS'),
        'ATHENA_DATABASE': os.environ.get('ATHENA_DATABASE'),
        'ATHENA_OUTPUT_BUCKET': os.environ.get('ATHENA_OUTPUT_BUCKET'),
        'TEAMS_INCOMING_WEBHOOK_URL': os.environ.get('TEAMS_INCOMING_WEBHOOK_URL')
    }
    
    # Check for missing variables
    missing_vars = [var for var, value in required_vars.items() 
                    if not value and var != 'CROSS_ACCOUNT_ROLE_NAME']
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return required_vars


def initialize_agent() -> AgentOrchestrator:
    """Initialize the agent orchestrator with credential manager."""
    global _agent_orchestrator, _credential_manager
    
    if _agent_orchestrator is not None:
        logger.info("Reusing existing agent orchestrator")
        return _agent_orchestrator
    
    try:
        logger.info("Initializing agent orchestrator")
        
        # Get environment variables
        env_vars = get_environment_variables()
        
        # Initialize credential manager
        if _credential_manager is None:
            _credential_manager = CredentialManager(env_vars['CROSS_ACCOUNT_ROLE_NAME'])
            logger.info("Credential manager initialized")
        
        # Initialize agent orchestrator
        _agent_orchestrator = AgentOrchestrator(
            credential_manager=_credential_manager,
            max_iterations=10,
            verbose=True,
            session_expiration_minutes=60
        )
        
        logger.info("Agent orchestrator initialized successfully")
        return _agent_orchestrator
        
    except Exception as e:
        logger.error(f"Failed to initialize agent: {str(e)}", exc_info=True)
        raise AgentOrchestratorError(f"Agent initialization failed: {str(e)}")


def parse_teams_webhook_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Teams Outgoing Webhook event or standard query format.
    
    Supports two formats:
    1. Teams Outgoing Webhook: {"body": "{\"type\":\"message\",\"text\":\"...\"}"}
    2. Standard query: {"query": "..."}
    
    Teams sends a payload like:
    {
        "type": "message",
        "text": "<at>AWSBot</at> 查詢 myapp 的 DNS",
        "from": {"name": "User Name", "id": "..."},
        "conversation": {"id": "..."},
        "recipient": {"name": "AWSBot"},
        ...
    }
    """
    try:
        # Handle API Gateway wrapper
        if 'body' in event:
            body_str = event.get('body', '{}')
            if isinstance(body_str, str):
                body = json.loads(body_str)
            else:
                body = body_str
        else:
            body = event
        
        # Check if this is a standard query format (not Teams webhook)
        if 'query' in body and 'type' not in body:
            # Standard query format - return as-is
            return {
                'query': body['query'].strip(),
                'user_name': 'Direct Invocation',
                'conversation_id': body.get('session_id', 'direct'),
                'original_body': body,
                'is_teams_webhook': False
            }
        
        # Teams webhook format
        # Extract message text
        text = body.get('text', '')
        
        # Remove bot mention from text
        # Teams format: "<at>BotName</at> actual query"
        if '<at>' in text and '</at>' in text:
            # Remove the mention tag
            import re
            text = re.sub(r'<at>.*?</at>\s*', '', text)
        
        text = text.strip()
        
        if not text:
            raise ValueError("Empty message text")
        
        # Extract user info
        from_user = body.get('from', {})
        user_name = from_user.get('name', 'Unknown User')
        
        # Extract conversation info for session tracking
        conversation = body.get('conversation', {})
        conversation_id = conversation.get('id', 'unknown')
        
        return {
            'query': text,
            'user_name': user_name,
            'conversation_id': conversation_id,
            'original_body': body,
            'is_teams_webhook': True
        }
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in request body: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse request: {str(e)}")


def send_teams_message(webhook_url: str, message: str, title: Optional[str] = None) -> bool:
    """Send message to Teams via Incoming Webhook or Power Automate using Adaptive Card.
    
    Uses the same format as the working dns-query.py script.
    
    Args:
        webhook_url: Teams Incoming Webhook URL or Power Automate webhook URL
        message: Message text to send
        title: Optional message title
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use the exact same format as dns-query.py that works
        data = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": []
                    }
                }
            ]
        }
        
        # Add title if provided
        if title:
            data["attachments"][0]["content"]["body"].append({
                "type": "TextBlock",
                "text": title,
                "size": "large",
                "weight": "bolder"
            })
        
        # Add message text
        data["attachments"][0]["content"]["body"].append({
            "type": "TextBlock",
            "text": message,
            "wrap": True
        })
        
        # Add timestamp
        from datetime import datetime
        data["attachments"][0]["content"]["body"].append({
            "type": "TextBlock",
            "text": f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "isSubtle": True
        })
        
        # Send to webhook
        logger.info(f"Sending to webhook URL: {webhook_url[:50]}...")
        response = requests.post(
            webhook_url,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        # Power Automate returns 202 Accepted, Teams returns 200 OK
        if response.status_code in [200, 202]:
            logger.info(f"Successfully sent message to webhook (status: {response.status_code})")
            return True
        else:
            logger.error(f"Failed to send to webhook: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending message to webhook: {str(e)}", exc_info=True)
        return False


def process_query_and_send_to_teams(query: str, conversation_id: str, user_name: str, webhook_url: str):
    """Process query and send result to Teams.
    
    This function is called by the async handler to process the actual query.
    """
    try:
        logger.info(f"Starting query processing for: {query}")
        start_time = datetime.utcnow()
        
        # Initialize agent
        agent = initialize_agent()
        
        # Execute query
        agent_result = agent.execute_query(
            query=query,
            session_id=conversation_id,
            request_id=f"teams_{conversation_id}_{int(start_time.timestamp())}"
        )
        
        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        logger.info(f"Agent result: success={agent_result.get('success')}, "
                     f"output_length={len(agent_result.get('output', ''))}, "
                     f"error={agent_result.get('error', 'none')}")
        
        # Format result for Teams
        if agent_result.get('success', False):
            output = agent_result.get('output', 'No output generated')
            
            # Truncate if too long for Teams Adaptive Card (max ~28KB)
            if len(output) > 25000:
                output = output[:25000] + "\n\n... (結果已截斷，過長)"
            
            # Format the response nicely
            title = "🤖 AWSBot 查詢結果"
            message = f"{output}\n\n⏱️ 執行時間: {execution_time}ms"
            
        else:
            error = agent_result.get('error', 'Unknown error')
            title = "❌ 查詢失敗"
            message = f"錯誤: {error}\n\n⏱️ 執行時間: {execution_time}ms"
        
        logger.info(f"Sending to Teams: title={title}, message_length={len(message)}")
        
        # Send result to Teams
        success = send_teams_message(webhook_url, message, title)
        
        if success:
            logger.info(f"Query processing completed and sent to Teams in {execution_time}ms")
        else:
            logger.error("Failed to send result to Teams")
        
    except Exception as e:
        logger.error(f"Error in query processing: {str(e)}", exc_info=True)
        
        # Send error message to Teams
        error_title = "❌ 系統錯誤"
        error_message = f"處理查詢時發生錯誤: {str(e)}"
        send_teams_message(webhook_url, error_message, error_title)


def invoke_async_lambda(function_name: str, payload: Dict[str, Any]):
    """Invoke Lambda function asynchronously."""
    import boto3
    
    try:
        lambda_client = boto3.client('lambda')
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Async Lambda invoked: {function_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to invoke async Lambda: {str(e)}", exc_info=True)
        return False


def verify_api_key(event: Dict[str, Any]) -> bool:
    """Verify API key from request headers or body.
    
    Returns True if:
    - API key matches the expected value
    - Or request is from async self-invocation
    - Or request is direct Lambda invoke (no requestContext)
    - Or API_KEY environment variable is not set (disabled)
    """
    expected_key = os.environ.get('API_KEY')
    
    # If API_KEY not configured, skip verification
    if not expected_key:
        return True
    
    # Skip verification for async self-invocation
    if event.get('async_processing', False):
        return True
    
    # Skip verification for direct Lambda invoke (no Function URL context)
    # Function URL requests have 'requestContext' with 'http' key
    request_context = event.get('requestContext', {})
    if not request_context.get('http'):
        # This is a direct Lambda invoke, not Function URL
        return True
    
    # Check headers (Function URL format)
    headers = event.get('headers', {})
    # Headers can be lowercase in Function URL
    api_key = headers.get('x-api-key') or headers.get('X-Api-Key')
    
    if api_key == expected_key:
        return True
    
    # Check body for API key (fallback)
    body = event.get('body', '{}')
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except:
            body = {}
    
    if body.get('api_key') == expected_key:
        return True
    
    return False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for Teams Outgoing Webhook.
    
    This handler supports two modes:
    
    1. Sync mode (initial webhook call):
       - Immediately returns "Processing..." to Teams (< 5 seconds)
       - Invokes itself asynchronously to process the query
       - Sends final result via Incoming Webhook
    
    2. Async mode (self-invoked):
       - Processes the actual query
       - Sends result to Teams via Incoming Webhook
    
    Args:
        event: API Gateway event containing Teams webhook payload
        context: Lambda execution context
        
    Returns:
        Immediate response to Teams Outgoing Webhook (sync mode)
        or processing result (async mode)
    """
    logger.info("Teams webhook handler started")
    
    # Verify API key for security
    if not verify_api_key(event):
        logger.warning("Invalid or missing API key")
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Forbidden: Invalid API key'})
        }
    
    # Check if this is an async invocation (processing mode)
    if event.get('async_processing', False):
        logger.info("Running in async processing mode")
        
        query = event['query']
        conversation_id = event['conversation_id']
        user_name = event['user_name']
        webhook_url = event['webhook_url']
        
        # Process query and send to Teams
        process_query_and_send_to_teams(query, conversation_id, user_name, webhook_url)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'completed'})
        }
    
    # Sync mode - handle initial webhook call or direct invocation
    try:
        # Get environment variables
        env_vars = get_environment_variables()
        webhook_url = env_vars['TEAMS_INCOMING_WEBHOOK_URL']
        
        # Parse request (supports both Teams webhook and standard query format)
        try:
            request_data = parse_teams_webhook_event(event)
            query = request_data['query']
            user_name = request_data['user_name']
            conversation_id = request_data['conversation_id']
            is_teams_webhook = request_data.get('is_teams_webhook', True)
            
            logger.info(f"Received query from {user_name}: {query}")
            logger.info(f"Request type: {'Teams webhook' if is_teams_webhook else 'Direct invocation'}")
            
        except ValueError as e:
            logger.warning(f"Invalid request: {str(e)}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'type': 'message',
                    'text': f'❌ 無效的請求: {str(e)}'
                })
            }
        
        # For direct invocation (not Teams webhook), process synchronously
        if not is_teams_webhook:
            logger.info("Processing direct invocation synchronously")
            start_time = datetime.utcnow()
            
            # Check if we should also send to Teams (default: False for direct invocations)
            send_to_teams = request_data.get('original_body', {}).get('send_to_teams', False)
            
            # Initialize agent
            agent = initialize_agent()
            
            # Execute query
            agent_result = agent.execute_query(
                query=query,
                session_id=conversation_id,
                request_id=f"direct_{conversation_id}_{int(start_time.timestamp())}"
            )
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Format result
            if agent_result.get('success', False):
                output = agent_result.get('output', 'No output generated')
                
                # Only send to Teams if explicitly requested
                if send_to_teams:
                    try:
                        title = "🤖 AWSBot 查詢結果"
                        message = f"{output}\n\n⏱️ 執行時間: {execution_time}ms"
                        send_success = send_teams_message(webhook_url, message, title)
                        if send_success:
                            logger.info("Result also sent to Teams")
                        else:
                            logger.warning("Failed to send result to Teams")
                    except Exception as e:
                        logger.error(f"Error sending to Teams: {str(e)}")
                
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'status': 'success',
                        'output': output,
                        'query': query,
                        'execution_time_ms': execution_time
                    })
                }
            else:
                error = agent_result.get('error', 'Unknown error')
                
                # Only send error to Teams if explicitly requested
                if send_to_teams:
                    try:
                        title = "❌ 查詢失敗"
                        message = f"錯誤: {error}\n\n⏱️ 執行時間: {execution_time}ms"
                        send_teams_message(webhook_url, message, title)
                    except Exception as e:
                        logger.error(f"Error sending error to Teams: {str(e)}")
                
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'status': 'error',
                        'error': error,
                        'query': query,
                        'execution_time_ms': execution_time
                    })
                }
        
        # For Teams webhook, use async processing
        # Invoke Lambda asynchronously to process the query
        function_name = context.function_name if hasattr(context, 'function_name') else os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        
        async_payload = {
            'async_processing': True,
            'query': query,
            'conversation_id': conversation_id,
            'user_name': user_name,
            'webhook_url': webhook_url
        }
        
        invoke_async_lambda(function_name, async_payload)
        
        # Return immediate response to Teams
        response_text = f"🔄 正在處理您的查詢...\n\n查詢: {query}\n\n請稍候，結果將在處理完成後顯示。"
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'type': 'message',
                'text': response_text
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in Teams webhook handler: {str(e)}", exc_info=True)
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'type': 'message',
                'text': f'❌ 系統錯誤: {str(e)}'
            })
        }
