"""
Athena CloudFront Logs Tool for AWS Operations Agent.

This module provides a LangChain tool for querying CloudFront access logs via Athena.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

from langchain_core.tools import tool, InjectedToolArg
from typing import Dict, Any, Optional, List, Annotated
from botocore.exceptions import ClientError
import time
import logging

logger = logging.getLogger(__name__)


@tool
def query_cloudfront_logs(
    credential_manager: Annotated[Any, InjectedToolArg],
    distribution_id: str,
    start_date: str,
    end_date: str,
    status_code_min: Optional[int] = None,
    status_code_max: Optional[int] = None,
    database: str = "centralized_logging",
    table: str = "cloudfront_standard_logs",
    output_bucket: Optional[str] = None,
    max_results: int = 100,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query CloudFront access logs from Athena.
    Use this tool to analyze CDN access patterns and errors.
    
    Args:
        distribution_id: CloudFront distribution ID (required)
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        status_code_min: Minimum HTTP status code (optional)
        status_code_max: Maximum HTTP status code (optional)
        database: Athena database name (default: centralized_logging)
        table: Athena table name (default: cloudfront_standard_logs)
        output_bucket: S3 bucket for Athena query results (optional)
        max_results: Maximum number of results to return (default: 100)
        
    Returns:
        JSON with CloudFront log entries
    """
    try:
        logger.info(f"Querying CloudFront logs - Distribution: {distribution_id}, Date range: {start_date} to {end_date}")
        
        # Get Athena client
        athena_client = credential_manager.get_boto3_client('athena')
        
        # Build SQL query
        sql_query = _build_cloudfront_logs_query(
            distribution_id=distribution_id,
            start_date=start_date,
            end_date=end_date,
            status_code_min=status_code_min,
            status_code_max=status_code_max,
            table=table,
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
        
        logger.info(f"Successfully retrieved {len(results)} CloudFront log records")
        
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
        logger.error(f"Unexpected error querying CloudFront logs: {str(e)}")
        return {
            "query_execution_id": None,
            "results": [],
            "result_count": 0,
            "error": f"Unexpected error: {str(e)}"
        }


def _build_cloudfront_logs_query(
    distribution_id: str,
    start_date: str,
    end_date: str,
    status_code_min: Optional[int] = None,
    status_code_max: Optional[int] = None,
    table: str = "cloudfront_standard_logs",
    max_results: int = 100
) -> str:
    """
    Build SQL query for CloudFront logs.
    
    Args:
        distribution_id: CloudFront distribution ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        status_code_min: Minimum HTTP status code
        status_code_max: Maximum HTTP status code
        table: Table name
        max_results: Maximum number of results
        
    Returns:
        SQL query string
    """
    # Base query with all required fields per requirements
    query = f"""
    SELECT
        date,
        time,
        cs_method,
        cs_host,
        cs_uri_stem,
        cs_uri_query,
        sc_status,
        x_edge_result_type,
        x_edge_detailed_result_type,
        time_taken,
        time_to_first_byte,
        x_edge_location,
        c_ip,
        x_forwarded_for
    FROM {table}
    WHERE distribution_id = '{distribution_id}'
    """
    
    # Add date range filter
    query += f"\n  AND date >= '{start_date}'"
    query += f"\n  AND date <= '{end_date}'"
    
    # Add status code filter if provided
    if status_code_min is not None and status_code_max is not None:
        query += f"\n  AND sc_status >= {status_code_min}"
        query += f"\n  AND sc_status <= {status_code_max}"
    elif status_code_min is not None:
        query += f"\n  AND sc_status >= {status_code_min}"
    elif status_code_max is not None:
        query += f"\n  AND sc_status <= {status_code_max}"
    
    # Add ordering and limit
    query += f"\nORDER BY date DESC, time DESC\nLIMIT {max_results}"
    
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
    column_names = None
    
    try:
        paginator = athena_client.get_paginator('get_query_results')
        
        for page in paginator.paginate(QueryExecutionId=query_execution_id):
            rows = page['ResultSet']['Rows']
            
            if column_names is None:  # First page
                # Extract column names from first row
                column_names = [col['VarCharValue'] for col in rows[0]['Data']]
                rows = rows[1:]  # Skip header row
            
            # Process data rows
            for row in rows:
                if 'Data' in row:
                    row_data = {}
                    for i, col in enumerate(row['Data']):
                        col_name = column_names[i]
                        row_data[col_name] = col.get('VarCharValue', '')
                    results.append(row_data)
        
        return results
        
    except ClientError as e:
        logger.error(f"Error getting query results: {e}")
        return []


class AthenaCloudFrontLogsTool:
    """
    Wrapper class for Athena CloudFront Logs tool that maintains credential manager reference.
    """
    
    def __init__(
        self,
        credential_manager,
        database: str = "centralized_logging",
        table: str = "cloudfront_standard_logs",
        output_bucket: Optional[str] = None
    ):
        """
        Initialize Athena CloudFront Logs tool with credential manager.
        
        Args:
            credential_manager: CredentialManager instance
            database: Athena database name
            table: Athena table name
            output_bucket: S3 bucket for query results
        """
        self.credential_manager = credential_manager
        self.database = database
        self.table = table
        self.output_bucket = output_bucket
    
    def query_logs(
        self,
        distribution_id: str,
        start_date: str,
        end_date: str,
        status_code_min: Optional[int] = None,
        status_code_max: Optional[int] = None,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """
        Query CloudFront logs.
        
        Args:
            distribution_id: CloudFront distribution ID
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            status_code_min: Minimum HTTP status code (optional)
            status_code_max: Maximum HTTP status code (optional)
            max_results: Maximum number of results (default: 100)
            
        Returns:
            Dictionary with CloudFront log results
        """
        return query_cloudfront_logs(
            self.credential_manager,
            distribution_id=distribution_id,
            start_date=start_date,
            end_date=end_date,
            status_code_min=status_code_min,
            status_code_max=status_code_max,
            database=self.database,
            table=self.table,
            output_bucket=self.output_bucket,
            max_results=max_results
        )
