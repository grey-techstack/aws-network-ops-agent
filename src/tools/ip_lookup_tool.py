"""
IP Lookup Tool for AWS Operations Agent.

This module provides IP address lookup capabilities:
1. AWS Elastic IP lookup - find associated resources
2. Corporate Network List lookup - check if IP is in the corporate network allowlist
3. Third-party IP geolocation - region, ISP, organization

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

import json
import logging
import re
import os
import ipaddress
from typing import Dict, Any, Optional, List, Annotated
from langchain_core.tools import tool, InjectedToolArg
from datetime import datetime

logger = logging.getLogger(__name__)

# SCP allowlist file path (bundled with Lambda)
SCP_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'corporate-network-whitelist.tf'
)


def _parse_scp_allowlist(file_path: str) -> List[Dict[str, str]]:
    """
    Parse the corporate-network-whitelist.tf file to extract IP entries with comments.
    
    Returns:
        List of dicts with 'ip', 'cidr', 'comment', 'section' keys
    """
    entries = []
    current_section = "Unknown"
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.warning(f"SCP file not found: {file_path}")
        return entries
    
    for line in lines:
        stripped = line.strip()
        
        # Track section headers (# SECTION NAME)
        section_match = re.match(r'^#\s+(.+)$', stripped)
        if section_match and not stripped.startswith('#"') and '//' not in stripped:
            section_text = section_match.group(1).strip()
            # Only update section if it looks like a header (not a comment on an IP)
            if not any(c in section_text for c in ['.', '/', ':']):
                current_section = section_text
        
        # Match IP entries: "x.x.x.x/32", or "x.x.x.x",
        ip_match = re.match(r'^\s*"(\d+\.\d+\.\d+\.\d+(?:/\d+)?)"', stripped)
        if ip_match:
            ip_cidr = ip_match.group(1)
            # Extract inline comment (// comment or # comment)
            comment = ""
            comment_match = re.search(r'(?://|#)\s*(.+)$', stripped)
            if comment_match:
                comment = comment_match.group(1).strip().rstrip(',').strip()
            
            # Normalize: add /32 if no CIDR
            if '/' not in ip_cidr:
                ip_only = ip_cidr
                ip_cidr = f"{ip_cidr}/32"
            else:
                ip_only = ip_cidr.split('/')[0]
            
            entries.append({
                'ip': ip_only,
                'cidr': ip_cidr,
                'comment': comment,
                'section': current_section
            })
    
    return entries


def _lookup_ip_in_scp(ip_address: str, entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Check if an IP address is in the SCP allowlist.
    Supports both exact match and CIDR range match.
    """
    matches = []
    try:
        target_ip = ipaddress.ip_address(ip_address)
    except ValueError:
        return matches
    
    for entry in entries:
        try:
            network = ipaddress.ip_network(entry['cidr'], strict=False)
            if target_ip in network:
                matches.append(entry)
        except ValueError:
            # Exact string match fallback
            if ip_address == entry['ip']:
                matches.append(entry)
    
    return matches


@tool
def lookup_ip_address(
    ip_address: str,
    credential_manager: Annotated[Any, InjectedToolArg],
    account_id: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Comprehensive IP address lookup tool. Queries multiple sources:
    1. AWS Elastic IP - finds associated EC2 instances, ENIs, NAT Gateways
    2. Corporate Network List - checks if IP is in the corporate network allowlist
    3. IP Geolocation - queries ip-api.com for region, ISP, organization info
    4. AWS IP Range - identifies if IP belongs to AWS and which service (EC2, CloudFront, S3, etc.)
    
    Use this when asked about any public IP address, its source, owner, or location.
    
    Args:
        ip_address: The public IP address to look up (e.g., '203.0.113.62')
        account_id: AWS account ID to search (optional, searches all configured accounts)
        
    Returns:
        JSON with results from all three lookup sources
        
    Examples:
        - "What is IP 203.0.113.61?" -> lookup_ip_address('203.0.113.61')
        - "Who owns 203.0.113.62?" -> lookup_ip_address('203.0.113.62')
        - "Is 203.0.113.55 in our allowlist?" -> lookup_ip_address('203.0.113.55')
    """
    start_time = datetime.utcnow()
    results = {
        'ip_address': ip_address,
        'aws_elastic_ip': None,
        'corporate_network_list': None,
        'geolocation': None
    }
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
    except ImportError:
        cloudwatch_logger = None
    
    # Validate IP address
    try:
        ipaddress.ip_address(ip_address)
    except ValueError:
        return {
            'success': False,
            'ip_address': ip_address,
            'error': f"Invalid IP address: {ip_address}"
        }
    
    # ========================================
    # 1. AWS Elastic IP Lookup
    # ========================================
    try:
        logger.info(f"Looking up Elastic IP: {ip_address}")
        
        # Determine accounts to search
        accounts_to_search = []
        if account_id:
            accounts_to_search.append(account_id)
        else:
            # Search primary account
            primary_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')
            if primary_account:
                accounts_to_search.append(primary_account)
            # Search workload accounts
            workload_ids = os.environ.get('WORKLOAD_ACCOUNT_IDS', '')
            if workload_ids:
                accounts_to_search.extend([a.strip() for a in workload_ids.split(',') if a.strip()])
            # Also search the Lambda's own account
            try:
                own_client = credential_manager.get_boto3_client('sts')
                own_account = own_client.get_caller_identity()['Account']
                if own_account not in accounts_to_search:
                    accounts_to_search.append(own_account)
            except Exception:
                pass
        
        eip_found = False
        for acct in accounts_to_search:
            try:
                ec2_client = credential_manager.get_boto3_client('ec2', account_id=acct)
                
                # Search Elastic IPs
                response = ec2_client.describe_addresses(
                    Filters=[{'Name': 'public-ip', 'Values': [ip_address]}]
                )
                
                if response.get('Addresses'):
                    addr = response['Addresses'][0]
                    
                    # Check if associated with NAT Gateway
                    nat_gateway_id = None
                    nat_gateway_name = None
                    eni_type = None
                    eni_description = None
                    eni_id = addr.get('NetworkInterfaceId')
                    
                    # Get ENI details (interface type, description)
                    if eni_id:
                        try:
                            eni_response = ec2_client.describe_network_interfaces(
                                NetworkInterfaceIds=[eni_id]
                            )
                            if eni_response.get('NetworkInterfaces'):
                                eni = eni_response['NetworkInterfaces'][0]
                                eni_type = eni.get('InterfaceType')
                                eni_description = eni.get('Description')
                        except Exception:
                            pass
                    
                    # Check NAT Gateway association
                    if eni_id and not addr.get('InstanceId'):
                        try:
                            nat_response = ec2_client.describe_nat_gateways(
                                Filters=[{'Name': 'nat-gateway-addresses.network-interface-id', 'Values': [eni_id]}]
                            )
                            if nat_response.get('NatGateways'):
                                nat_gw = nat_response['NatGateways'][0]
                                nat_gateway_id = nat_gw.get('NatGatewayId')
                                nat_tags = {t['Key']: t['Value'] for t in nat_gw.get('Tags', [])}
                                nat_gateway_name = nat_tags.get('Name', '')
                        except Exception:
                            pass
                    
                    results['aws_elastic_ip'] = {
                        'found': True,
                        'account_id': acct,
                        'allocation_id': addr.get('AllocationId'),
                        'association_id': addr.get('AssociationId'),
                        'instance_id': addr.get('InstanceId'),
                        'nat_gateway_id': nat_gateway_id,
                        'nat_gateway_name': nat_gateway_name,
                        'network_interface_id': eni_id,
                        'interface_type': eni_type,
                        'interface_description': eni_description,
                        'private_ip': addr.get('PrivateIpAddress'),
                        'public_dns': addr.get('PublicDns', f"ec2-{ip_address.replace('.', '-')}.ap-southeast-1.compute.amazonaws.com"),
                        'domain': addr.get('Domain'),
                        'tags': {t['Key']: t['Value'] for t in addr.get('Tags', [])},
                        'network_border_group': addr.get('NetworkBorderGroup')
                    }
                    eip_found = True
                    break
                    
            except Exception as e:
                logger.debug(f"Error searching account {acct}: {str(e)}")
                continue
        
        if not eip_found:
            # Also check if it's a NAT Gateway IP or ENI public IP
            for acct in accounts_to_search:
                try:
                    ec2_client = credential_manager.get_boto3_client('ec2', account_id=acct)
                    
                    # Search Network Interfaces by public IP
                    eni_response = ec2_client.describe_network_interfaces(
                        Filters=[{'Name': 'association.public-ip', 'Values': [ip_address]}]
                    )
                    
                    if eni_response.get('NetworkInterfaces'):
                        eni = eni_response['NetworkInterfaces'][0]
                        results['aws_elastic_ip'] = {
                            'found': True,
                            'type': 'network_interface',
                            'account_id': acct,
                            'network_interface_id': eni.get('NetworkInterfaceId'),
                            'interface_type': eni.get('InterfaceType'),
                            'description': eni.get('Description'),
                            'private_ip': eni.get('PrivateIpAddress'),
                            'subnet_id': eni.get('SubnetId'),
                            'vpc_id': eni.get('VpcId'),
                            'availability_zone': eni.get('AvailabilityZone'),
                            'status': eni.get('Status'),
                            'attachment': {
                                'instance_id': eni.get('Attachment', {}).get('InstanceId'),
                                'status': eni.get('Attachment', {}).get('Status')
                            } if eni.get('Attachment') else None,
                            'tags': {t['Key']: t['Value'] for t in eni.get('TagSet', [])}
                        }
                        eip_found = True
                        break
                except Exception as e:
                    logger.debug(f"Error searching ENIs in account {acct}: {str(e)}")
                    continue
        
        if not eip_found:
            results['aws_elastic_ip'] = None
            
    except Exception as e:
        logger.error(f"Error in AWS EIP lookup: {str(e)}")
        results['aws_elastic_ip'] = {
            'found': False,
            'error': str(e)
        }
    
    # ========================================
    # 2. Corporate Network List Lookup
    # ========================================
    try:
        logger.info(f"Checking Corporate network list for: {ip_address}")
        entries = _parse_scp_allowlist(SCP_FILE_PATH)
        
        if entries:
            matches = _lookup_ip_in_scp(ip_address, entries)
            if matches:
                results['corporate_network_list'] = {
                    'found': True,
                    'matches': matches,
                    'total_entries_in_file': len(entries)
                }
            else:
                results['corporate_network_list'] = None
        else:
            results['corporate_network_list'] = None
            
    except Exception as e:
        logger.error(f"Error in Corporate network list lookup: {str(e)}")
        results['corporate_network_list'] = {
            'found': False,
            'error': str(e)
        }
    
    # ========================================
    # 3. IP Geolocation (ip-api.com - free, no API key)
    # ========================================
    try:
        logger.info(f"Looking up geolocation for: {ip_address}")
        import urllib.request
        
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,regionName,city,zip,lat,lon,timezone,isp,org,as,query,reverse"
        req = urllib.request.Request(url, headers={'User-Agent': 'AWS-Ops-Agent/1.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())
        
        if geo_data.get('status') == 'success':
            results['geolocation'] = {
                'found': True,
                'country': geo_data.get('country'),
                'region': geo_data.get('regionName'),
                'city': geo_data.get('city'),
                'timezone': geo_data.get('timezone'),
                'isp': geo_data.get('isp'),
                'organization': geo_data.get('org'),
                'as_number': geo_data.get('as'),
                'reverse_dns': geo_data.get('reverse'),
                'latitude': geo_data.get('lat'),
                'longitude': geo_data.get('lon')
            }
        else:
            results['geolocation'] = {
                'found': False,
                'message': geo_data.get('message', 'Geolocation lookup failed')
            }
            
    except Exception as e:
        logger.error(f"Error in geolocation lookup: {str(e)}")
        results['geolocation'] = {
            'found': False,
            'error': f"Geolocation lookup failed: {str(e)}"
        }
    
    # ========================================
    # 4. AWS IP Range Identification (skip if EIP already found)
    # ========================================
    if not results.get('aws_elastic_ip'):
        try:
            logger.info(f"Checking AWS IP ranges for: {ip_address}")
            import urllib.request
            
            aws_url = "https://ip-ranges.amazonaws.com/ip-ranges.json"
            req = urllib.request.Request(aws_url, headers={'User-Agent': 'AWS-Ops-Agent/1.0'})
            
            with urllib.request.urlopen(req, timeout=5) as response:
                aws_data = json.loads(response.read().decode())
            
            target_ip = ipaddress.ip_address(ip_address)
            aws_matches = []
            
            for prefix in aws_data.get('prefixes', []):
                try:
                    network = ipaddress.ip_network(prefix['ip_prefix'], strict=False)
                    if target_ip in network:
                        aws_matches.append({
                            'cidr': prefix['ip_prefix'],
                            'region': prefix.get('region'),
                            'service': prefix.get('service'),
                            'network_border_group': prefix.get('network_border_group')
                        })
                except (ValueError, KeyError):
                    continue
            
            if aws_matches:
                # Deduplicate by service
                services = list(set(m['service'] for m in aws_matches))
                regions = list(set(m['region'] for m in aws_matches))
                results['aws_ip_range'] = {
                    'found': True,
                    'is_aws_ip': True,
                    'services': services,
                    'regions': regions,
                    'matches': aws_matches[:5]  # Limit to 5 most relevant
                }
            else:
                results['aws_ip_range'] = None
                
        except Exception as e:
            logger.debug(f"AWS IP range check failed (non-critical): {str(e)}")
            results['aws_ip_range'] = None
    else:
        results['aws_ip_range'] = None
    
    # ========================================
    # Build summary
    # ========================================
    execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    results['success'] = True
    results['execution_time_ms'] = execution_time_ms
    
    if cloudwatch_logger:
        try:
            cloudwatch_logger.log_tool_execution(
                tool_name='lookup_ip_address',
                parameters={'ip_address': ip_address},
                execution_time_ms=execution_time_ms,
                success=True,
                request_id=request_id,
                result_summary=f"IP lookup for {ip_address}: AWS={'found' if results.get('aws_elastic_ip') else 'no'}, Corp={'found' if results.get('corporate_network_list') else 'no'}, Geo={'found' if results.get('geolocation') else 'no'}"
            )
        except Exception:
            pass
    
    logger.info(f"IP lookup completed for {ip_address} in {execution_time_ms}ms")
    return results
