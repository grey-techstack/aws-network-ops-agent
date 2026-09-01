"""
Route53 Tool for AWS Operations Agent.

This module provides a LangChain tool for querying Route53 DNS records.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

import os
from langchain_core.tools import tool, InjectedToolArg
from typing import Dict, Any, Optional, Annotated
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


@tool
def query_route53_records(
    fqdn: str,
    credential_manager: Annotated[Any, InjectedToolArg],
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query Route53 DNS records for a fully qualified domain name (FQDN).
    
    Args:
        fqdn: The FQDN to look up DNS records for.
        
    Returns:
        JSON with hosted zone info and DNS records (A, CNAME, ALIAS)
    
    IMPORTANT - When tracing end-to-end flow:
    - Use the F5 origin server DNS as the fqdn parameter (NOT the user's original FQDN).
    - Example: F5 origin is d2chk-preprod.apse1.dgt.np-api.example.com → query this, not uat-ecapi.example.com
    - If FQDN ends with .internal.example.com → query the internal.example.com hosted zone directly.
    
    NEXT STEP - Based on DNS record value ending:
    - *.elb.amazonaws.com → query_load_balancer / describe_load_balancer_listeners
    - *.cloudfront.net → query_cloudfront_distribution
    - ves-io-*.ac.vh.ves.io → query_f5_load_balancer / query_f5_origin_pool
    - *.internal.example.com → query_route53_records (internal.example.com zone)
    - Otherwise → execute_aws_cli_command
    """
    from datetime import datetime
    start_time = datetime.utcnow()
    
    try:
        # Import here to avoid circular imports
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info(f"Querying Route53 records for FQDN: {fqdn}")
        
        # Get Core Network Account ID from environment - Route53 hosted zones are there
        core_network_account_id = os.environ.get('CORE_NETWORK_ACCOUNT_ID')
        
        # Get Route53 client - use Core Network Account for hosted zones
        route53_client = credential_manager.get_boto3_client(
            'route53', 
            account_id=core_network_account_id,
            request_id=request_id
        )
        
        # Find the hosted zone for this FQDN
        hosted_zone = _find_hosted_zone(route53_client, fqdn)
        
        if not hosted_zone:
            logger.warning(f"No hosted zone found for FQDN: {fqdn}")
            
            # Log tool execution
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='query_route53_records',
                parameters={'fqdn': fqdn},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=f"No hosted zone found for {fqdn}"
            )
            
            return {
                "fqdn": fqdn,
                "hosted_zone_id": None,
                "hosted_zone_name": None,
                "records": [],
                "error": f"No hosted zone found for {fqdn}"
            }
        
        # Get DNS records for the FQDN
        records = _get_dns_records(
            route53_client,
            hosted_zone['Id'],
            fqdn
        )
        
        result = {
            "fqdn": fqdn,
            "hosted_zone_id": hosted_zone['Id'],
            "hosted_zone_name": hosted_zone['Name'],
            "records": records
        }
        
        # Log successful tool execution
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='query_route53_records',
            parameters={'fqdn': fqdn},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found {len(records)} DNS records"
        )
        
        logger.info(f"Successfully retrieved {len(records)} records for {fqdn}")
        return result
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Route53 API error: {error_code} - {error_message}")
        
        # Log failed tool execution
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_route53_records',
                parameters={'fqdn': fqdn},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=f"Route53 API error: {error_code}"
            )
        except ImportError:
            pass
        
        return {
            "fqdn": fqdn,
            "hosted_zone_id": None,
            "hosted_zone_name": None,
            "records": [],
            "error": f"Route53 API error: {error_code} - {error_message}"
        }
    
    except Exception as e:
        logger.error(f"Unexpected error querying Route53: {str(e)}")
        
        # Log failed tool execution
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_route53_records',
                parameters={'fqdn': fqdn},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=str(e)
            )
        except ImportError:
            pass
        
        return {
            "fqdn": fqdn,
            "hosted_zone_id": None,
            "hosted_zone_name": None,
            "records": [],
            "error": f"Unexpected error: {str(e)}"
        }


@tool
def list_route53_hosted_zones(
    credential_manager: Annotated[Any, InjectedToolArg],
    account_id: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    List Route53 hosted zones in an AWS account. Defaults to CORE_NETWORK_ACCOUNT_ID.

    Args:
        account_id: Optional AWS account ID (12 digits)

    Returns:
        JSON with hosted zones (id, name, private flag, record count)
    """
    from datetime import datetime
    start_time = datetime.utcnow()

    # Import here to avoid circular imports
    from src.agent.cloudwatch_logger import cloudwatch_logger

    # Prefer explicit account_id if valid; otherwise fall back to CORE_NETWORK_ACCOUNT_ID
    target_account = account_id
    if target_account:
        target_account = str(target_account).strip()
        if (
            target_account.upper() == 'CORE_NETWORK_ACCOUNT_ID'
            or not target_account.isdigit()
            or len(target_account) != 12
        ):
            target_account = None

    if not target_account:
        target_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')

    try:
        logger.info(
            "Listing Route53 hosted zones",
            extra={"target_account": target_account, "request_id": request_id}
        )

        route53_client = credential_manager.get_boto3_client(
            'route53',
            account_id=target_account,
            request_id=request_id
        )

        hosted_zones = []
        paginator = route53_client.get_paginator('list_hosted_zones')

        for page in paginator.paginate():
            for zone in page.get('HostedZones', []):
                hosted_zones.append({
                    "id": zone.get('Id'),
                    "name": zone.get('Name'),
                    "private_zone": zone.get('Config', {}).get('PrivateZone', False),
                    "record_count": zone.get('ResourceRecordSetCount'),
                    "comment": zone.get('Config', {}).get('Comment')
                })

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_route53_hosted_zones',
            parameters={'account_id': target_account},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found {len(hosted_zones)} hosted zones"
        )

        return {
            "account_id": target_account,
            "hosted_zones": hosted_zones,
            "count": len(hosted_zones)
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Route53 API error: {error_code} - {error_message}")

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_route53_hosted_zones',
            parameters={'account_id': target_account},
            execution_time_ms=execution_time_ms,
            success=False,
            request_id=request_id,
            error_message=f"Route53 API error: {error_code}"
        )

        return {
            "account_id": target_account,
            "hosted_zones": [],
            "count": 0,
            "error": f"Route53 API error: {error_code} - {error_message}"
        }

    except Exception as e:
        logger.error(f"Unexpected error listing Route53 hosted zones: {str(e)}")

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_route53_hosted_zones',
            parameters={'account_id': target_account},
            execution_time_ms=execution_time_ms,
            success=False,
            request_id=request_id,
            error_message=str(e)
        )

        return {
            "account_id": target_account,
            "hosted_zones": [],
            "count": 0,
            "error": f"Unexpected error: {str(e)}"
        }


@tool
def list_route53_hosted_zone_records(
    credential_manager: Annotated[Any, InjectedToolArg],
    hosted_zone_id: Optional[str] = None,
    zone_name: Optional[str] = None,
    account_id: Optional[str] = None,
    name_contains: Optional[str] = None,
    type_filter: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    List DNS records in a Route53 hosted zone with optional filtering.
    
    WHEN TO USE THIS TOOL:
    - When user asks for DNS records "related to" or "containing" a keyword (e.g., "any DNS record related to webapp")
      → Use name_contains to search within a hosted zone (e.g., zone_name='internal.example.com', name_contains='webapp')
    - When user wants to browse or search records inside a specific hosted zone
    - Do NOT confuse with query_route53_records (which looks up a specific FQDN)

    Args:
        hosted_zone_id: Hosted zone ID (preferred)
        zone_name: Hosted zone name (e.g., internal.example.com) if ID not provided
        account_id: Optional AWS account ID (defaults to CORE_NETWORK_ACCOUNT_ID)
        name_contains: Substring filter on record names — use this when searching by keyword
        type_filter: Optional record type filter (A, CNAME, ALIAS, etc.)

    Returns:
        JSON with hosted_zone_id, hosted_zone_name, records[], count
    """
    from datetime import datetime
    start_time = datetime.utcnow()

    from src.agent.cloudwatch_logger import cloudwatch_logger

    # Normalize account_id; fallback to core account
    target_account = account_id
    if target_account:
        target_account = str(target_account).strip()
        if target_account.upper() == 'CORE_NETWORK_ACCOUNT_ID' or not target_account.isdigit() or len(target_account) != 12:
            target_account = None
    if not target_account:
        target_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')

    try:
        route53_client = credential_manager.get_boto3_client(
            'route53',
            account_id=target_account,
            request_id=request_id
        )

        zone_id = hosted_zone_id
        zone_name_resolved = None

        # Resolve zone by name if ID not provided
        if not zone_id and zone_name:
            zone = _find_hosted_zone_by_name(route53_client, zone_name)
            if zone:
                zone_id = zone.get('Id')
                zone_name_resolved = zone.get('Name')
        elif zone_id:
            zone_name_resolved = zone_name

        if not zone_id:
            raise ValueError("hosted_zone_id or zone_name is required")

        records = _list_records_in_zone(
            route53_client,
            zone_id,
            name_contains=name_contains,
            type_filter=type_filter
        )

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_route53_hosted_zone_records',
            parameters={'hosted_zone_id': zone_id, 'zone_name': zone_name, 'account_id': target_account},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found {len(records)} records"
        )

        return {
            "account_id": target_account,
            "hosted_zone_id": zone_id,
            "hosted_zone_name": zone_name_resolved,
            "records": records,
            "count": len(records)
        }

    except Exception as e:
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_route53_hosted_zone_records',
            parameters={'hosted_zone_id': hosted_zone_id, 'zone_name': zone_name, 'account_id': target_account},
            execution_time_ms=execution_time_ms,
            success=False,
            request_id=request_id,
            error_message=str(e)
        )

        return {
            "account_id": target_account,
            "hosted_zone_id": hosted_zone_id,
            "hosted_zone_name": zone_name,
            "records": [],
            "count": 0,
            "error": str(e)
        }


def _find_hosted_zone(route53_client, fqdn: str) -> Optional[Dict[str, Any]]:
    """
    Find the hosted zone that matches the FQDN.
    
    Args:
        route53_client: boto3 Route53 client
        fqdn: Fully qualified domain name
        
    Returns:
        Hosted zone dictionary or None if not found
    """
    # Normalize FQDN (ensure it ends with a dot for Route53)
    if not fqdn.endswith('.'):
        fqdn_normalized = fqdn + '.'
    else:
        fqdn_normalized = fqdn
    
    try:
        # List all hosted zones
        paginator = route53_client.get_paginator('list_hosted_zones')
        
        # Find the most specific hosted zone that matches
        best_match = None
        best_match_length = 0
        
        for page in paginator.paginate():
            for zone in page['HostedZones']:
                zone_name = zone['Name']
                
                # Check if FQDN ends with this zone name
                if fqdn_normalized.endswith(zone_name):
                    # Keep track of the most specific match (longest zone name)
                    if len(zone_name) > best_match_length:
                        best_match = zone
                        best_match_length = len(zone_name)
        
        return best_match
        
    except ClientError as e:
        logger.error(f"Error listing hosted zones: {e}")
        return None


def _find_hosted_zone_by_name(route53_client, zone_name: str) -> Optional[Dict[str, Any]]:
    """Find a hosted zone by its name (exact match)."""
    normalized = zone_name.rstrip('.') + '.'
    try:
        paginator = route53_client.get_paginator('list_hosted_zones')
        for page in paginator.paginate():
            for zone in page.get('HostedZones', []):
                if zone.get('Name') == normalized:
                    return zone
        return None
    except ClientError as e:
        logger.error(f"Error listing hosted zones by name: {e}")
        return None


def _get_dns_records(
    route53_client,
    hosted_zone_id: str,
    fqdn: str
) -> list:
    """
    Get DNS records for a specific FQDN from a hosted zone.
    
    Args:
        route53_client: boto3 Route53 client
        hosted_zone_id: Hosted zone ID
        fqdn: Fully qualified domain name
        
    Returns:
        List of DNS record dictionaries
    """
    # Normalize FQDN
    if not fqdn.endswith('.'):
        fqdn_normalized = fqdn + '.'
    else:
        fqdn_normalized = fqdn
    
    records = []
    
    try:
        # List resource record sets for the hosted zone
        paginator = route53_client.get_paginator('list_resource_record_sets')
        
        for page in paginator.paginate(HostedZoneId=hosted_zone_id):
            for record_set in page['ResourceRecordSets']:
                # Check if this record matches our FQDN
                if record_set['Name'] == fqdn_normalized:
                    record_type = record_set['Type']
                    
                    # Handle different record types
                    if record_type in ['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS']:
                        # Standard records with ResourceRecords
                        if 'ResourceRecords' in record_set:
                            for resource_record in record_set['ResourceRecords']:
                                records.append({
                                    "type": record_type,
                                    "value": resource_record['Value'],
                                    "ttl": record_set.get('TTL', 0)
                                })
                    
                    # Handle ALIAS records
                    if 'AliasTarget' in record_set:
                        alias_target = record_set['AliasTarget']
                        records.append({
                            "type": "ALIAS",
                            "value": alias_target['DNSName'].rstrip('.'),
                            "ttl": 0,  # ALIAS records don't have TTL
                            "alias_hosted_zone_id": alias_target['HostedZoneId'],
                            "evaluate_target_health": alias_target.get('EvaluateTargetHealth', False)
                        })
        
        return records
        
    except ClientError as e:
        logger.error(f"Error listing resource record sets: {e}")
        return []


def _list_records_in_zone(
    route53_client,
    hosted_zone_id: str,
    name_contains: Optional[str] = None,
    type_filter: Optional[str] = None
) -> list:
    """
    List records in a hosted zone with optional filtering.
    """
    records = []
    name_filter = name_contains.lower() if name_contains else None
    type_filter_norm = type_filter.upper() if type_filter else None

    try:
        paginator = route53_client.get_paginator('list_resource_record_sets')
        for page in paginator.paginate(HostedZoneId=hosted_zone_id):
            for record_set in page.get('ResourceRecordSets', []):
                rec_name = record_set.get('Name', '').rstrip('.')
                rec_type = record_set.get('Type', '')

                if name_filter and name_filter not in rec_name.lower():
                    continue
                if type_filter_norm and rec_type.upper() != type_filter_norm:
                    continue

                entry = {
                    "name": rec_name,
                    "type": rec_type,
                    "ttl": record_set.get('TTL', 0)
                }

                if 'ResourceRecords' in record_set:
                    entry['values'] = [rr.get('Value') for rr in record_set['ResourceRecords']]

                if 'AliasTarget' in record_set:
                    alias = record_set['AliasTarget']
                    entry['alias_target'] = {
                        "dns_name": alias.get('DNSName', '').rstrip('.'),
                        "hosted_zone_id": alias.get('HostedZoneId'),
                        "evaluate_target_health": alias.get('EvaluateTargetHealth', False)
                    }

                records.append(entry)

        return records

    except ClientError as e:
        logger.error(f"Error listing resource record sets: {e}")
        return []


class Route53Tool:
    """
    Wrapper class for Route53 tool that maintains credential manager reference.
    """
    
    def __init__(self, credential_manager):
        """
        Initialize Route53 tool with credential manager.
        """
        self.credential_manager = credential_manager

    def query_records(self, fqdn: str) -> Dict[str, Any]:
        """Query Route53 records for an FQDN."""
        return query_route53_records(fqdn, self.credential_manager)

    def list_hosted_zones(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """List hosted zones in the target account (defaults to CORE_NETWORK_ACCOUNT_ID)."""
        return list_route53_hosted_zones(
            credential_manager=self.credential_manager,
            account_id=account_id
        )

