"""
LangChain Agent Orchestrator for AWS Operations Agent.

This module provides the main agent orchestration logic using LangChain v1.2.6 API
with LangGraph for agent execution.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from src.agent.bedrock_client import create_bedrock_llm, BedrockClientError
from src.agent.prompts import AGENT_SYSTEM_PROMPT
from src.agent.session_manager import SessionManager
from src.credentials.credential_manager import CredentialManager

logger = logging.getLogger(__name__)


class AgentOrchestratorError(Exception):
    """Exception raised for agent orchestration errors."""
    pass


class AgentOrchestrator:
    """
    Orchestrates the LangChain agent with AWS tools using LangGraph.
    
    Uses the modern LangChain v1.2.6 API with:
    - @tool decorator for tool definitions
    - langgraph.prebuilt.create_react_agent for agent execution
    - bind_tools() for tool binding
    """
    
    def __init__(
        self,
        credential_manager: CredentialManager,
        llm=None,
        max_iterations: int = 10,
        verbose: bool = True,
        session_expiration_minutes: int = 60
    ):
        """
        Initialize the agent orchestrator.
        
        Args:
            credential_manager: CredentialManager for AWS authentication
            llm: Optional pre-configured LLM (if None, creates Bedrock LLM)
            max_iterations: Maximum agent iterations (default: 10)
            verbose: Enable verbose logging (default: True)
            session_expiration_minutes: Session expiration time in minutes
        """
        self.credential_manager = credential_manager
        self.max_iterations = max_iterations
        self.verbose = verbose
        self._current_request_id = 'unknown'
        
        # Initialize session manager
        self.session_manager = SessionManager(expiration_minutes=session_expiration_minutes)
        
        # Initialize LLM
        if llm is None:
            try:
                self.llm = create_bedrock_llm()
            except BedrockClientError as e:
                logger.error(f"Failed to create Bedrock LLM: {str(e)}")
                raise AgentOrchestratorError(f"Failed to initialize LLM: {str(e)}")
        else:
            self.llm = llm
        
        # Create tools with credential manager injected
        self.tools = self._create_tools()
        
        # Create agent using LangGraph
        self.agent = self._create_agent()
        
        logger.info(
            f"Agent orchestrator initialized with {len(self.tools)} tools, "
            f"max_iterations={max_iterations}, verbose={verbose}"
        )
    
    def _create_tools(self) -> List:
        """
        Create tools with credential manager injected using InjectedToolArg.
        
        Tools are defined in src/tools/*.py with InjectedToolArg for credential_manager.
        We use inject_tool_args to bind the credential_manager at runtime.
        
        Returns:
            List of tool functions with injected dependencies
        """
        logger.info("Creating agent tools with InjectedToolArg")
        
        # Import tools from src/tools/
        from src.tools.route53_tool import (
            query_route53_records,
            list_route53_hosted_zones,
            list_route53_hosted_zone_records
        )
        from src.tools.cloudfront_tool import query_cloudfront_distribution
        from src.tools.elb_tool import query_load_balancer, describe_load_balancer_listeners
        from src.tools.athena_vpc_flow_logs_tool import query_vpc_flow_logs
        from src.tools.athena_cloudfront_logs_tool import query_cloudfront_logs
        from src.tools.f5_waf_tool import (
            query_f5_load_balancer,
            query_f5_origin_pool,
            list_f5_load_balancers,
            query_f5_load_balancer_by_name,
            list_f5_namespaces
        )
        from src.tools.aws_cli_tool import execute_aws_cli_command
        from src.tools.ip_lookup_tool import lookup_ip_address
        
        # Store reference to self for closure
        orchestrator = self
        
        # Create a wrapper to inject credential_manager and request_id
        def inject_args(tool_func):
            """Wrap tool to inject credential_manager and request_id."""
            import functools
            import inspect
            
            # Determine which injected params this function actually accepts
            sig = inspect.signature(tool_func.func)
            func_params = set(sig.parameters.keys())
            
            @functools.wraps(tool_func.func)
            def wrapper(*args, **kwargs):
                # Only inject params the function actually accepts
                if 'credential_manager' in func_params:
                    kwargs['credential_manager'] = orchestrator.credential_manager
                if 'request_id' in func_params:
                    kwargs['request_id'] = orchestrator._current_request_id
                result = tool_func.func(*args, **kwargs)
                return json.dumps(result, default=str) if isinstance(result, dict) else result
            
            # Create new tool with same metadata but wrapped function
            from langchain_core.tools import StructuredTool
            from pydantic import create_model
            
            # Get the schema and remove injected fields (Pydantic v2 compatible)
            original_schema = tool_func.get_input_schema()
            injected_fields = {'credential_manager', 'request_id'}
            
            # Build clean fields using model_fields (Pydantic v2)
            clean_fields = {}
            model_fields = getattr(original_schema, 'model_fields', None) or getattr(original_schema, '__fields__', {})
            for field_name, field_info in model_fields.items():
                if field_name not in injected_fields:
                    annotation = original_schema.__annotations__.get(field_name, str)
                    clean_fields[field_name] = (annotation, field_info)
            
            # Create new pydantic model without injected fields
            if clean_fields:
                CleanSchema = create_model(
                    f"{tool_func.name}_Schema",
                    **clean_fields
                )
            else:
                CleanSchema = create_model(f"{tool_func.name}_Schema")
            
            return StructuredTool(
                name=tool_func.name,
                description=tool_func.description,
                func=wrapper,
                args_schema=CleanSchema
            )
        
        # Wrap all tools
        tools = [
            inject_args(query_route53_records),
            inject_args(list_route53_hosted_zones),
            inject_args(list_route53_hosted_zone_records),
            inject_args(query_cloudfront_distribution),
            inject_args(query_load_balancer),
            inject_args(describe_load_balancer_listeners),
            inject_args(query_vpc_flow_logs),
            inject_args(query_cloudfront_logs),
            inject_args(query_f5_load_balancer),
            inject_args(query_f5_origin_pool),
            inject_args(list_f5_load_balancers),
            inject_args(query_f5_load_balancer_by_name),
            inject_args(list_f5_namespaces),
            inject_args(execute_aws_cli_command),
            inject_args(lookup_ip_address),
        ]
        
        logger.info(f"Created {len(tools)} tools with InjectedToolArg")
        return tools
    
    def _create_agent(self):
        """
        Create the ReAct agent using LangGraph.
        
        Returns:
            LangGraph agent executor
        """
        logger.info("Creating LangGraph ReAct agent")
        
        try:
            # Create agent using LangGraph's create_react_agent
            # This automatically handles tool binding and execution loop
            agent = create_react_agent(
                self.llm,
                tools=self.tools,
            )
            
            logger.info("LangGraph ReAct agent created successfully")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            raise AgentOrchestratorError(f"Failed to create agent: {str(e)}")
    
    def _extract_entities_from_response(self, response: str) -> Dict[str, Any]:
        """
        Extract key entities (domain, ALB, target group, etc.) from agent response.
        
        Args:
            response: Agent response text
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        
        # Extract domain names (e.g., myapp.internal.example.com)
        domain_patterns = [
            r'(?:domain|FQDN|DNS)[:\s]+([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+)',
            r'([a-zA-Z0-9][-a-zA-Z0-9]*\.internal\.example\.com)',
            r'([a-zA-Z0-9][-a-zA-Z0-9]*\.example\.com)',
        ]
        for pattern in domain_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                entities['domain'] = match.group(1)
                break
        
        # Extract ALB DNS names
        alb_pattern = r'(internal-[a-zA-Z0-9-]+\.ap-southeast-1\.elb\.amazonaws\.com|[a-zA-Z0-9-]+\.ap-southeast-1\.elb\.amazonaws\.com)'
        alb_match = re.search(alb_pattern, response)
        if alb_match:
            entities['alb_dns'] = alb_match.group(1)
        
        # Extract ALB names (e.g., internal-alb-app-01)
        alb_name_pattern = r'(?:ALB|Load Balancer)[:\s]+([a-zA-Z0-9-]+(?:alb|nlb)[a-zA-Z0-9-]*)'
        alb_name_match = re.search(alb_name_pattern, response, re.IGNORECASE)
        if alb_name_match:
            entities['alb_name'] = alb_name_match.group(1)
        
        # Extract Target Group ARNs
        tg_pattern = r'(arn:aws:elasticloadbalancing:[a-z0-9-]+:\d+:targetgroup/[a-zA-Z0-9-]+/[a-zA-Z0-9]+)'
        tg_match = re.search(tg_pattern, response)
        if tg_match:
            entities['target_group_arn'] = tg_match.group(1)
        
        # Extract CloudFront distribution IDs
        cf_pattern = r'(?:Distribution|CloudFront)[:\s]+([A-Z0-9]{13,14})'
        cf_match = re.search(cf_pattern, response)
        if cf_match:
            entities['cloudfront_id'] = cf_match.group(1)
        
        return entities
    
    def _enrich_query_with_context(self, query: str, session_id: str) -> str:
        """
        Enrich a follow-up query with context from previous conversation.
        
        Args:
            query: Original user query
            session_id: Session ID for context lookup
            
        Returns:
            Enriched query with context
        """
        # Get session and check for stored entities
        session = self.session_manager.get_session(session_id)
        if not session:
            return query
        
        # Check if query is a follow-up (contains pronouns or references)
        follow_up_indicators = [
            'that domain', 'the domain', 'this domain',
            'that alb', 'the alb', 'this alb',
            'that load balancer', 'the load balancer',
            'target health', 'the target', 'its target',
            'same', 'it', 'its', 'the'
        ]
        
        query_lower = query.lower()
        is_follow_up = any(indicator in query_lower for indicator in follow_up_indicators)
        
        if not is_follow_up:
            return query
        
        # Get entities from session metadata
        entities = session.metadata.get('entities', {})
        
        if not entities:
            # Try to extract from last assistant response
            history = session.get_conversation_history()
            for msg in reversed(history):
                if msg.get('role') == 'assistant':
                    entities = self._extract_entities_from_response(msg.get('content', ''))
                    if entities:
                        session.metadata['entities'] = entities
                        break
        
        if not entities:
            return query
        
        # Build context prefix
        context_parts = []
        if 'domain' in entities:
            context_parts.append(f"domain {entities['domain']}")
        if 'alb_dns' in entities:
            context_parts.append(f"ALB {entities['alb_dns']}")
        if 'target_group_arn' in entities:
            context_parts.append(f"target group {entities['target_group_arn']}")
        
        if context_parts:
            context_str = ", ".join(context_parts)
            enriched_query = f"[Context: We were discussing {context_str}] {query}"
            logger.info(f"Enriched query: {enriched_query}")
            return enriched_query
        
        return query
    
    def execute_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        request_id: str = 'unknown'
    ) -> Dict[str, Any]:
        """
        Execute a user query using the agent.
        
        Args:
            query: Natural language query from user
            session_id: Optional session ID for conversation context
            request_id: Request ID for logging
            
        Returns:
            Dictionary containing output, intermediate_steps, session_id, success
        """
        self._current_request_id = request_id
        
        logger.info(f"Executing query: {query} (session_id: {session_id}, request_id: {request_id})")
        
        try:
            # Enrich query with context if this is a follow-up
            enriched_query = query
            if session_id:
                enriched_query = self._enrich_query_with_context(query, session_id)
                # Add user message to session (original query for display)
                self.session_manager.add_user_message(session_id, query)
            
            # Build messages with system prompt and enriched user query
            messages = [
                SystemMessage(content=AGENT_SYSTEM_PROMPT),
                HumanMessage(content=enriched_query)
            ]
            
            # Execute agent using LangGraph
            result = self.agent.invoke(
                {"messages": messages},
                {"recursion_limit": self.max_iterations * 2}
            )
            
            # Extract final response from messages
            final_messages = result.get("messages", [])
            output = ""
            intermediate_steps = []
            
            for msg in final_messages:
                if not hasattr(msg, 'content'):
                    continue
                if isinstance(msg, AIMessage):
                    # Collect tool calls for intermediate steps
                    tool_calls = getattr(msg, 'tool_calls', None) or []
                    if tool_calls:
                        for tc in tool_calls:
                            intermediate_steps.append({
                                'tool': tc.get('name', 'unknown'),
                                'input': tc.get('args', {})
                            })
                    # AI message with content and no tool calls = final answer
                    if msg.content and not tool_calls:
                        output = msg.content
            
            # Fallback: use last AI message with content
            if not output:
                for msg in reversed(final_messages):
                    if isinstance(msg, AIMessage) and msg.content:
                        output = msg.content
                        break
            
            logger.info(f"Extracted output length: {len(output)}, intermediate_steps: {len(intermediate_steps)}")
            
            # Add assistant response to session and extract entities
            if session_id and output:
                self.session_manager.add_assistant_message(session_id, output)
                
                # Extract and store entities for future follow-up queries
                entities = self._extract_entities_from_response(output)
                if entities:
                    session = self.session_manager.get_session(session_id)
                    if session:
                        # Merge with existing entities (new ones take precedence)
                        existing = session.metadata.get('entities', {})
                        existing.update(entities)
                        session.metadata['entities'] = existing
                        logger.info(f"Stored entities for session {session_id}: {existing}")
            
            logger.info("Query executed successfully")
            return {
                "output": output,
                "intermediate_steps": intermediate_steps,
                "session_id": session_id,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}", exc_info=True)

            # Fallback: if model tool-use failed, try direct hosted zone listing
            if "hosted zone" in query.lower():
                try:
                    fallback = list_route53_hosted_zones.func(
                        credential_manager=self.credential_manager,
                        account_id=None,
                        request_id=request_id
                    )
                    summary = (
                        f"Found {fallback.get('count', 0)} hosted zones in core account"
                        if fallback.get("error") is None else fallback.get("error")
                    )
                    return {
                        "output": summary,
                        "intermediate_steps": [
                            {
                                "tool": "list_route53_hosted_zones",
                                "input": {"account_id": None}
                            }
                        ],
                        "session_id": session_id,
                        "success": fallback.get("error") is None,
                        "error": fallback.get("error")
                    }
                except Exception as fallback_error:
                    logger.error(f"Fallback hosted zone listing failed: {fallback_error}")

            if session_id:
                self.session_manager.add_assistant_message(
                    session_id,
                    f"Error: {str(e)}",
                    metadata={"error": True}
                )
            
            return {
                "output": "",
                "intermediate_steps": [],
                "session_id": session_id,
                "success": False,
                "error": str(e)
            }
        finally:
            self._current_request_id = 'unknown'
    
    def get_tool_names(self) -> List[str]:
        """Get list of available tool names."""
        return [t.name for t in self.tools]
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get dictionary of tool names and descriptions."""
        return {t.name: t.description for t in self.tools}

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session."""
        return self.session_manager.get_session_info(session_id)
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a specific session."""
        return self.session_manager.clear_session(session_id)
    
    def get_active_session_count(self) -> int:
        """Get the number of active sessions."""
        return self.session_manager.get_active_session_count()
