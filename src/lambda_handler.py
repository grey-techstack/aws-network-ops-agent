"""AWS Lambda handler for the Operations Agent.

This module provides the main entry point for the Lambda function that
orchestrates the AI-powered AWS operations assistant.
"""

import json
import logging
import os
import signal
from typing import Any, Dict, Optional
from datetime import datetime

from src.agent.simple_agent import SimpleAgent
from src.agent.agent_orchestrator import AgentOrchestrator, AgentOrchestratorError
from src.agent.error_handlers import ErrorHandler
from src.agent.formatters import FQDNTraceFormatter, LogQueryFormatter
from src.agent.cloudwatch_logger import cloudwatch_logger
from src.credentials.credential_manager import CredentialManager

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variables for Lambda container reuse
_agent_orchestrator: Optional[AgentOrchestrator] = None
_credential_manager: Optional[CredentialManager] = None


class LambdaTimeoutHandler:
    """Handle Lambda timeout gracefully."""
    
    def __init__(self, context):
        self.context = context
        self.timeout_occurred = False
    
    def timeout_handler(self, signum, frame):
        """Handle timeout signal."""
        self.timeout_occurred = True
        logger.warning("Lambda function approaching timeout")
    
    def setup_timeout_handler(self):
        """Set up timeout handler with 30-second buffer."""
        if hasattr(self.context, 'get_remaining_time_in_millis'):
            remaining_time = self.context.get_remaining_time_in_millis()
            timeout_buffer = 30000  # 30 seconds
            
            if remaining_time > timeout_buffer:
                signal.alarm(int((remaining_time - timeout_buffer) / 1000))
                signal.signal(signal.SIGALRM, self.timeout_handler)


def get_environment_variables() -> Dict[str, str]:
    """Get and validate required environment variables."""
    required_vars = {
        'CROSS_ACCOUNT_ROLE_NAME': os.environ.get('CROSS_ACCOUNT_ROLE_NAME', 'aws-ops-agent-cross-account-role'),
        'F5_SECRET_NAME': os.environ.get('F5_SECRET_NAME'),
        'CORE_NETWORK_ACCOUNT_ID': os.environ.get('CORE_NETWORK_ACCOUNT_ID'),
        'WORKLOAD_ACCOUNT_IDS': os.environ.get('WORKLOAD_ACCOUNT_IDS'),
    }
    
    # Check for missing variables (CROSS_ACCOUNT_ROLE_NAME has default)
    missing_vars = [var for var, value in required_vars.items() 
                    if not value and var != 'CROSS_ACCOUNT_ROLE_NAME']
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        logger.error("Please ensure all required environment variables are set. See ENVIRONMENT_VARIABLES.md for details.")
        raise ValueError(error_msg)
    
    # Validate CORE_NETWORK_ACCOUNT_ID format
    core_account_id = required_vars['CORE_NETWORK_ACCOUNT_ID']
    if not core_account_id.isdigit() or len(core_account_id) != 12:
        error_msg = f"Invalid CORE_NETWORK_ACCOUNT_ID format: {core_account_id}. Expected 12-digit AWS Account ID"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate WORKLOAD_ACCOUNT_IDS format
    workload_account_ids = required_vars['WORKLOAD_ACCOUNT_IDS']
    account_ids = [aid.strip() for aid in workload_account_ids.split(',')]
    for account_id in account_ids:
        if not account_id.isdigit() or len(account_id) != 12:
            error_msg = f"Invalid WORKLOAD_ACCOUNT_IDS format: {workload_account_ids}. Each account ID must be a 12-digit number"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    
    logger.info("All environment variables validated successfully")
    logger.info(f"Cross Account Role: {required_vars['CROSS_ACCOUNT_ROLE_NAME']}")
    logger.info(f"F5 Secret: {required_vars['F5_SECRET_NAME']}")
    logger.info(f"Core Network Account: {core_account_id}")
    logger.info(f"Workload Accounts: {len(account_ids)} accounts configured")
    
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


def parse_api_gateway_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse API Gateway event and extract request data."""
    try:
        # Handle different event formats
        if 'body' in event:
            # Standard API Gateway event
            body_str = event.get('body', '{}')
            if isinstance(body_str, str):
                body = json.loads(body_str)
            else:
                body = body_str
        else:
            # Direct invocation or test event
            body = event
        
        # Extract required fields
        query = body.get('query')
        session_id = body.get('session_id')
        max_results = body.get('max_results', 100)
        
        # Validate query
        if not query or not isinstance(query, str):
            raise ValueError("Missing or invalid 'query' field")
        
        if query.strip() == "":
            raise ValueError("Query cannot be empty")
        
        return {
            'query': query.strip(),
            'session_id': session_id,
            'max_results': max_results,
            'request_id': event.get('requestContext', {}).get('requestId', 'unknown'),
            'source_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        }
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in request body: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse request: {str(e)}")


def format_agent_response(
    agent_result: Dict[str, Any],
    request_data: Dict[str, Any],
    execution_time_ms: int
) -> Dict[str, Any]:
    """Format agent response for API Gateway."""
    try:
        if not agent_result.get('success', False):
            # Agent execution failed
            error_message = agent_result.get('error', 'Unknown error')
            return {
                'status': 'error',
                'error_message': error_message,
                'query': request_data['query'],
                'session_id': request_data.get('session_id'),
                'timestamp': datetime.utcnow().isoformat(),
                'execution_time_ms': execution_time_ms
            }
        
        # Agent execution succeeded
        output = agent_result.get('output', '')
        intermediate_steps = agent_result.get('intermediate_steps', [])
        
        # Try to parse the output to determine result type and format accordingly
        formatted_output = output
        result_type = 'text'
        
        # Check if output contains structured data that can be formatted
        try:
            # Look for JSON-like structures in the output
            if 'trace_path' in output.lower() or 'fqdn' in output.lower():
                result_type = 'fqdn_trace'
            elif 'log' in output.lower() and ('vpc' in output.lower() or 'cloudfront' in output.lower()):
                result_type = 'log_query'
            elif 'ip' in output.lower() and 'investigation' in output.lower():
                result_type = 'ip_investigation'
        except:
            # If parsing fails, keep as text
            pass
        
        return {
            'status': 'success',
            'result_type': result_type,
            'output': formatted_output,
            'query': request_data['query'],
            'session_id': request_data.get('session_id'),
            'intermediate_steps': intermediate_steps,
            'timestamp': datetime.utcnow().isoformat(),
            'execution_time_ms': execution_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to format agent response: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error_message': f'Failed to format response: {str(e)}',
            'query': request_data['query'],
            'session_id': request_data.get('session_id'),
            'timestamp': datetime.utcnow().isoformat(),
            'execution_time_ms': execution_time_ms
        }


def create_api_gateway_response(
    status_code: int,
    body: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Create properly formatted API Gateway response."""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, default=str)
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for agent orchestration.
    
    Args:
        event: API Gateway event containing user query
        context: Lambda execution context
        
    Returns:
        API Gateway response with agent results
    """
    start_time = datetime.utcnow()
    request_id = event.get('requestContext', {}).get('requestId', 'unknown')
    source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
    
    # Set up timeout handler
    timeout_handler = LambdaTimeoutHandler(context)
    timeout_handler.setup_timeout_handler()
    
    logger.info(f"Lambda handler started - Request ID: {request_id}")
    
    # Log operation start
    cloudwatch_logger.log_operation_start(
        operation='lambda_handler',
        request_id=request_id,
        source_ip=source_ip
    )
    
    try:
        # Handle OPTIONS request for CORS
        if event.get('httpMethod') == 'OPTIONS':
            return create_api_gateway_response(200, {'message': 'CORS preflight'})
        
        # Parse request
        try:
            request_data = parse_api_gateway_event(event)
            logger.info(f"Parsed request - Query: {request_data['query'][:100]}...")
            
            # Log operation start with query details
            cloudwatch_logger.log_operation_start(
                operation='query_processing',
                request_id=request_id,
                user_query=request_data['query'],
                session_id=request_data.get('session_id'),
                source_ip=source_ip
            )
            
        except ValueError as e:
            logger.warning(f"Invalid request: {str(e)}")
            cloudwatch_logger.log_error_with_context(
                error=e,
                operation='request_parsing',
                context={'event': event},
                request_id=request_id,
                include_stack_trace=False
            )
            return create_api_gateway_response(400, {
                'status': 'error',
                'error_type': 'validation',
                'error_message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Check for timeout before proceeding
        if timeout_handler.timeout_occurred:
            logger.warning("Timeout occurred before agent initialization")
            cloudwatch_logger.log_operation_complete(
                operation='query_processing',
                request_id=request_id,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                success=False,
                error_message='Timeout before agent initialization'
            )
            return create_api_gateway_response(408, {
                'status': 'error',
                'error_type': 'timeout',
                'error_message': 'Request timed out before processing could begin',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Initialize agent
        try:
            agent = initialize_agent()
            cloudwatch_logger.log_operation_complete(
                operation='agent_initialization',
                request_id=request_id,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                success=True
            )
        except Exception as e:
            logger.error(f"Agent initialization failed: {str(e)}", exc_info=True)
            cloudwatch_logger.log_error_with_context(
                error=e,
                operation='agent_initialization',
                context={'request_id': request_id},
                request_id=request_id
            )
            error_response = ErrorHandler.handle_unexpected_error(
                e, 'agent_initialization', 'initialize',
                context={'request_id': request_id}
            )
            return create_api_gateway_response(500, error_response)
        
        # Check for timeout before executing query
        if timeout_handler.timeout_occurred:
            logger.warning("Timeout occurred before query execution")
            cloudwatch_logger.log_operation_complete(
                operation='query_processing',
                request_id=request_id,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                success=False,
                error_message='Timeout before query execution'
            )
            return create_api_gateway_response(408, {
                'status': 'error',
                'error_type': 'timeout',
                'error_message': 'Request timed out before query execution',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Execute query
        try:
            logger.info(f"Executing query: {request_data['query']}")
            query_start_time = datetime.utcnow()
            
            agent_result = agent.execute_query(
                query=request_data['query'],
                session_id=request_data.get('session_id'),
                request_id=request_id
            )
            
            query_execution_time = int((datetime.utcnow() - query_start_time).total_seconds() * 1000)
            
            # Log query execution completion
            cloudwatch_logger.log_operation_complete(
                operation='agent_query_execution',
                request_id=request_id,
                execution_time_ms=query_execution_time,
                success=agent_result.get('success', False),
                result_type='agent_response',
                error_message=agent_result.get('error') if not agent_result.get('success', False) else None
            )
            
            logger.info("Query execution completed")
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}", exc_info=True)
            cloudwatch_logger.log_error_with_context(
                error=e,
                operation='query_execution',
                context={
                    'request_id': request_id,
                    'query': request_data['query'],
                    'session_id': request_data.get('session_id')
                },
                request_id=request_id
            )
            error_response = ErrorHandler.handle_unexpected_error(
                e, 'query_execution', 'execute_query',
                context={
                    'request_id': request_id,
                    'query': request_data['query'],
                    'session_id': request_data.get('session_id')
                }
            )
            return create_api_gateway_response(500, error_response)
        
        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Format response
        response_body = format_agent_response(agent_result, request_data, execution_time_ms)
        
        # Log successful completion
        cloudwatch_logger.log_operation_complete(
            operation='query_processing',
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            success=True,
            result_type=response_body.get('result_type', 'unknown')
        )
        
        logger.info(f"Request completed successfully - Execution time: {execution_time_ms}ms")
        
        return create_api_gateway_response(200, response_body)
        
    except Exception as e:
        # Handle any unexpected errors
        end_time = datetime.utcnow()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        logger.error(f"Unexpected error in Lambda handler: {str(e)}", exc_info=True)
        
        # Log the unexpected error
        cloudwatch_logger.log_error_with_context(
            error=e,
            operation='lambda_handler',
            context={'event': event, 'request_id': request_id},
            request_id=request_id
        )
        
        cloudwatch_logger.log_operation_complete(
            operation='query_processing',
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            success=False,
            error_message=str(e)
        )
        
        error_response = {
            'status': 'error',
            'error_type': 'internal',
            'error_message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat(),
            'execution_time_ms': execution_time_ms,
            'request_id': request_id
        }
        
        return create_api_gateway_response(500, error_response)
    
    finally:
        # Clean up timeout handler
        signal.alarm(0)
        
        # Log final operation completion
        end_time = datetime.utcnow()
        total_execution_time = int((end_time - start_time).total_seconds() * 1000)
        
        cloudwatch_logger.log_operation_complete(
            operation='lambda_handler',
            request_id=request_id,
            execution_time_ms=total_execution_time,
            success=True  # If we reach here, the handler completed (even if with errors)
        )
