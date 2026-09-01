"""
Simplified Agent using new LangChain API.
"""

import logging
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agent.bedrock_client import create_bedrock_llm

logger = logging.getLogger(__name__)


class SimpleAgent:
    """Simple agent using LangGraph create_react_agent API."""
    
    def __init__(self, tools: List):
        self.tools = tools
        self.llm = create_bedrock_llm()
        
        # Create agent using LangGraph
        self.agent = create_react_agent(self.llm, tools=self.tools)
        
        logger.info("Simple agent created successfully")
    
    def execute_query(self, query: str, session_id: str = None) -> Dict[str, Any]:
        """Execute a query using the agent."""
        try:
            logger.info(f"Executing query: {query}")
            
            # Execute the agent using LangGraph format
            result = self.agent.invoke(
                {"messages": [("human", query)]},
                {"recursion_limit": 10}
            )
            
            # Extract the response
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                output = last_message.content if hasattr(last_message, 'content') else str(last_message)
            else:
                output = "No response generated"
            
            return {
                'success': True,
                'output': output,
                'intermediate_steps': []
            }
            
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'output': '',
                'intermediate_steps': []
            }