"""
Athena VPC Flow Logs Tool for AWS Operations Agent.

This module provides a LangChain tool for querying VPC Flow Logs via Athena.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

from langchain_core.tools import tool, InjectedToolArg
from typing import Dict, Any, Optional, List, Annotated
from botocore.exceptions import ClientError
import time
import logging

logger = logging.getLogger(__name__)


@tool
def query_vpc_flow_logs(
    credential_manager: Annotated[Any, InjectedToolArg],
    request_id: Annotated[str, InjectedToolArg] = 'unknown',
    source_ip: Optional[str] = None,
    destination_ip: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    database: str = "centralized_logging",
    output_bucket: Optional[str] = None,
    max_results: int = 100
) -> Dict[str, Any]:
    """
    Query VPC Flow Logs from Athena to analyze network traffic.
    Use this tool to investigate network connections and traffic patterns.
    
    Args:
        source_ip: Source IP address to filter (optional)
        destination_ip: Destination IP address to filter (optional)
        start_time: Start time in ISO format (optional)
        end_time: End time in ISO format (optional)
        database: Athena database name (default: centralized_logging)
        output_bucket: S3 bucket for Athena query results (optional)
        max_results: Maximum number of results to return (default: 100)
        
    Returns:
        JSON with flow log entries including timestamps, IPs, ports, actions
    """
    try:
        logger.info(f"Querying VPC Flow Logs - Source: {source_ip}, Dest: {destination_ip}")
        
        # Get Athena client
        athena_client = credential_manager.get_boto3_client('athena')
        
        # Build SQL query
        sql_query = _build_vpc_flow_logs_query(
            source_ip=source_ip,
            destination_ip=destination_ip,
            start_time=start_time,
            end_time=end_time,
            max_results=max_results
        )
        
        logger.debug(f"Athena SQL query: {sql_query}")
        
        # Determine output location
        if not output_bucket:
            # Try to get from environment or use default
            import os
            output_bucket = os.environ.get('ATHENA_OUTPUT_BUCKET', 's3://aws-athena-query-results-default/')
        
        if not output_bucket.startswith('s3://'):
            output_bucket = f's3://{output_bucket}/'
        
        # Execute Athena query
        query_execution_id = _execute_athena_query(
            athena_client,
            sql_query,
            database,
            output_bucket
        )
        
        if not query_execution_id:
            return {
                "query_execution_id": None,
                "results": [],
                "result_count": 0,
                "error": "Failed to execute Athena query"
            }
        
        # Wait for query to complete
        query_status = _wait_for_query_completion(
            athena_client,
            query_execution_id,
            timeout_seconds=300
        )
        
        if query_status != 'SUCCEEDED':
            error_msg = f"Query failed with status: {query_status}"
            logger.error(error_msg)
            return {
                "query_execution_id": query_execution_id,
                "results": [],
                "result_count": 0,
                "error": error_msg
            }
        
        # Get query results
        results = _get_query_results(athena_client, query_execution_id)
        
        logger.info(f"Successfully retrieved {len(results)} VPC flow log records")
        
        return {
            "query_execution_id": query_execution_id,
            "results": results,
            "result_count": len(results)
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Athena API error: {error_code} - {error_message}")
        
        return {
            "query_execution_id": None,
            "results": [],
            "result_count": 0,
            "error": f"Athena API error: {error_code} - {error_message}"
        }
    
    except Exception as e:
        logger.error(f"Unexpected error querying VPC Flow Logs: {str(e)}")
        return {
            "query_execution_id": None,
            "results": [],
            "result_count": 0,
            "error": f"Unexpected error: {str(e)}"
        }


def _build_vpc_flow_logs_query(
    source_ip: Optional[str] = None,
    destination_ip: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    max_results: int = 100
) -> str:
    """
    Build SQL query for VPC Flow Logs.
    
    Args:
        source_ip: Source IP address filter
        destination_ip: Destination IP address filter
        start_time: Start time filter
        end_time: End time filter
        max_results: Maximum number of results
        
    Returns:
        SQL query string
    """
    # Base query
    query = """
    SELECT
        from_unixtime(start) as timestamp,
        srcaddr as source_ip,
        dstaddr as destination_ip,
        srcport as source_port,
        dstport as destination_port,
        protocol,
        packets,
        bytes,
        action
    FROM vpc_flow_logs
    WHERE 1=1
    """
    
    # Add filters
    conditions = []
    
    if source_ip:
        conditions.append(f"srcaddr = '{source_ip}'")
    
    if destination_ip:
        conditions.append(f"dstaddr = '{destination_ip}'")
    
    if start_time:
        # Convert ISO format to Unix timestamp if needed
        conditions.append(f"start >= unix_timestamp(timestamp '{start_time}')")
    
    if end_time:
        conditions.append(f"start <= unix_timestamp(timestamp '{end_time}')")
    
    # Add conditions to query
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    # Add ordering and limit
    query += f"\nORDER BY start DESC\nLIMIT {max_results}"
    
    return query


def _execute_athena_query(
    athena_client,
    query: str,
    database: str,
    output_location: str
) -> Optional[str]:
    """
    Execute an Athena query.
    
    Args:
        athena_client: boto3 Athena client
        query: SQL query string
        database: Database name
        output_location: S3 output location
        
    Returns:
        Query execution ID or None if failed
    """
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location}
        )
        
        query_execution_id = response['QueryExecutionId']
        logger.info(f"Started Athena query: {query_execution_id}")
        
        return query_execution_id
        
    except ClientError as e:
        logger.error(f"Error starting Athena query: {e}")
        return None


def _wait_for_query_completion(
    athena_client,
    query_execution_id: str,
    timeout_seconds: int = 300,
    poll_interval: int = 2
) -> str:
    """
    Wait for Athena query to complete.
    
    Args:
        athena_client: boto3 Athena client
        query_execution_id: Query execution ID
        timeout_seconds: Maximum time to wait
        poll_interval: Seconds between status checks
        
    Returns:
        Final query status (SUCCEEDED, FAILED, CANCELLED, TIMED_OUT)
    """
    start_time = time.time()
    
    while True:
        # Check if timeout exceeded
        if time.time() - start_time > timeout_seconds:
            logger.error(f"Query timeout after {timeout_seconds} seconds")
            return 'TIMED_OUT'
        
        try:
            response = athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            
            status = response['QueryExecution']['Status']['State']
            
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                if status == 'FAILED':
                    reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    logger.error(f"Query failed: {reason}")
                return status
            
            # Query still running, wait before checking again
            time.sleep(poll_interval)
            
        except ClientError as e:
            logger.error(f"Error checking query status: {e}")
            return 'FAILED'


def _get_query_results(
    athena_client,
    query_execution_id: str
) -> List[Dict[str, Any]]:
    """
    Get results from a completed Athena query.
    
    Args:
        athena_client: boto3 Athena client
        query_execution_id: Query execution ID
        
    Returns:
        List of result dictionaries
    """
    results = []
    
    try:
        paginator = athena_client.get_paginator('get_query_results')
        
        for page in paginator.paginate(QueryExecutionId=query_execution_id):
            # First row contains column names, skip it
            rows = page['ResultSet']['Rows']
            
            if not results:  # First page
                # Extract column names from first row
                column_names = [col['VarCharValue'] for col in rows[0]['Data']]
                rows = rows[1:]  # Skip header row
            else:
                column_names = None  # Already have column names
            
            # Process data rows
            for row in rows:
                if 'Data' in row:
                    row_data = {}
                    for i, col in enumerate(row['Data']):
                        col_name = column_names[i] if column_names else f'col_{i}'
                        row_data[col_name] = col.get('VarCharValue', '')
                    results.append(row_data)
        
        return results
        
    except ClientError as e:
        logger.error(f"Error getting query results: {e}")
        return []


class AthenaVPCFlowLogsTool:
    """
    Wrapper class for Athena VPC Flow Logs tool that maintains credential manager reference.
    """
    
    def __init__(self, credential_manager, database: str = "centralized_logging", output_bucket: Optional[str] = None):
        """
        Initialize Athena VPC Flow Logs tool with credential manager.
        
        Args:
            credential_manager: CredentialManager instance
            database: Athena database name
            output_bucket: S3 bucket for query results
        """
        self.credential_manager = credential_manager
        self.database = database
        self.output_bucket = output_bucket
    
    def query_flow_logs(
        self,
        source_ip: Optional[str] = None,
        destination_ip: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """
        Query VPC Flow Logs.
        
        Args:
            source_ip: Source IP address (optional)
            destination_ip: Destination IP address (optional)
            start_time: Start time in ISO format (optional)
            end_time: End time in ISO format (optional)
            max_results: Maximum number of results (default: 100)
            
        Returns:
            Dictionary with flow log results
        """
        return query_vpc_flow_logs(
            self.credential_manager,
            source_ip=source_ip,
            destination_ip=destination_ip,
            start_time=start_time,
            end_time=end_time,
            database=self.database,
            output_bucket=self.output_bucket,
            max_results=max_results
        )
