"""
ELB Tool for AWS Operations Agent.

This module provides a LangChain tool for querying ALB/NLB load balancers.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

from langchain_core.tools import tool, InjectedToolArg
from typing import Dict, Any, Optional, List, Annotated
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


@tool
def query_load_balancer(
    credential_manager: Annotated[Any, InjectedToolArg],
    dns_name: Optional[str] = None,
    fqdn: Optional[str] = None,
    account_id: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query ALB/NLB details, target groups, and health status.
    Use this tool to get load balancer configuration and backend target health.
    
    Args:
        dns_name: Load balancer DNS name (e.g., my-alb.us-east-1.elb.amazonaws.com)
        fqdn: FQDN to match against listener rule host headers. Can be the original domain (e.g., partner.example.com) or the Route53/F5 origin DNS (e.g., d2chk-preprod.apse1.dgt.np-api.example.com). Pass BOTH the original FQDN and the origin DNS separated by comma if available (e.g., "partner.example.com,d2chk-preprod.apse1.dgt.np-api.example.com").
        account_id: AWS account ID to search in (optional)
        
    Returns:
        JSON with load balancer details, matching listener rule, and target group health
    """
    try:
        logger.info(f"Querying load balancer - DNS: {dns_name}, Account: {account_id}")
        
        # Normalize account_id; fall back to CORE_NETWORK_ACCOUNT_ID when placeholder/invalid
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
            import os
            target_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')

        # Get ELBv2 client
        elbv2_client = credential_manager.get_boto3_client(
            'elbv2',
            account_id=target_account
        )
        
        # Find load balancer
        if dns_name:
            load_balancer = _find_load_balancer_by_dns(elbv2_client, dns_name)
        else:
            return {
                "error": "dns_name must be provided"
            }
        
        if not load_balancer:
            error_msg = f"Load balancer not found for DNS: {dns_name}"
            logger.warning(error_msg)
            return {
                "load_balancer_arn": None,
                "load_balancer_name": None,
                "dns_name": dns_name,
                "type": None,
                "scheme": None,
                "vpc_id": None,
                "account_id": target_account,
                "target_groups": [],
                "error": error_msg
            }
        
        # Extract load balancer details
        lb_arn = load_balancer['LoadBalancerArn']
        
        # If FQDN provided, find matching listener rule and its target group
        matched_target_groups = []
        matched_rule = None
        if fqdn:
            try:
                listeners_resp = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn)
                # Support comma-separated FQDNs (original + origin DNS)
                fqdn_list = [f.strip().lower().rstrip('.') for f in fqdn.split(',') if f.strip()]
                
                for listener in listeners_resp.get('Listeners', []):
                    rules_resp = elbv2_client.describe_rules(ListenerArn=listener['ListenerArn'])
                    
                    for rule in rules_resp.get('Rules', []):
                        if rule.get('IsDefault', False):
                            continue
                        
                        # Check host header conditions
                        for cond in rule.get('Conditions', []):
                            host_values = []
                            if cond.get('HostHeaderConfig'):
                                host_values = [h.lower() for h in cond['HostHeaderConfig'].get('Values', [])]
                            
                            # Match any of the FQDNs against host header values
                            matched = any(
                                f in host_values or any(f.endswith(h.replace('*', '')) for h in host_values if '*' in h)
                                for f in fqdn_list
                            )
                            if matched:
                                matched_rule = {
                                    'priority': rule.get('Priority'),
                                    'host_header': host_values,
                                    'listener_port': listener.get('Port'),
                                    'listener_protocol': listener.get('Protocol')
                                }
                                
                                # Get target groups from this rule's actions
                                for action in rule.get('Actions', []):
                                    if action.get('Type') == 'forward':
                                        # Single target group
                                        tg_arn = action.get('TargetGroupArn')
                                        if tg_arn:
                                            matched_target_groups.append(tg_arn)
                                        # Forward config with multiple target groups
                                        for tg in action.get('ForwardConfig', {}).get('TargetGroups', []):
                                            if tg.get('TargetGroupArn'):
                                                matched_target_groups.append(tg['TargetGroupArn'])
                                break
                        if matched_rule:
                            break
                    if matched_rule:
                        break
            except Exception as e:
                logger.warning(f"Failed to match listener rules for {fqdn}: {e}")
        
        # Get target groups - filtered if FQDN matched, otherwise all
        if matched_target_groups:
            target_groups = []
            for tg_arn in matched_target_groups:
                try:
                    tg_resp = elbv2_client.describe_target_groups(TargetGroupArns=[tg_arn])
                    for tg in tg_resp['TargetGroups']:
                        targets = _get_target_health(elbv2_client, tg_arn)
                        target_groups.append({
                            "target_group_arn": tg_arn,
                            "target_group_name": tg['TargetGroupName'],
                            "protocol": tg['Protocol'],
                            "port": tg['Port'],
                            "health_check_path": tg.get('HealthCheckPath', '/'),
                            "target_type": tg.get('TargetType', 'instance'),
                            "targets": targets
                        })
                except Exception as e:
                    logger.warning(f"Failed to get target group {tg_arn}: {e}")
        else:
            target_groups = _get_target_groups(elbv2_client, lb_arn)
        
        # Extract account ID from ARN
        extracted_account_id = lb_arn.split(':')[4]
        
        result = {
            "load_balancer_arn": lb_arn,
            "load_balancer_name": load_balancer['LoadBalancerName'],
            "dns_name": load_balancer['DNSName'],
            "type": load_balancer['Type'],
            "scheme": load_balancer['Scheme'],
            "vpc_id": load_balancer['VpcId'],
            "account_id": extracted_account_id,
            "availability_zones": [
                {
                    "zone_name": az['ZoneName'],
                    "subnet_id": az['SubnetId']
                }
                for az in load_balancer.get('AvailabilityZones', [])
            ],
            "matched_rule": matched_rule,
            "target_groups": target_groups
        }
        
        logger.info(f"Successfully retrieved load balancer: {result['load_balancer_name']}")
        return result
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"ELB API error: {error_code} - {error_message}")
        
        return {
            "load_balancer_arn": None,
            "load_balancer_name": None,
            "dns_name": dns_name,
            "type": None,
            "scheme": None,
            "vpc_id": None,
            "account_id": account_id,
            "target_groups": [],
            "error": f"ELB API error: {error_code} - {error_message}"
        }
    
    except Exception as e:
        logger.error(f"Unexpected error querying ELB: {str(e)}")
        return {
            "load_balancer_arn": None,
            "load_balancer_name": None,
            "dns_name": dns_name,
            "type": None,
            "scheme": None,
            "vpc_id": None,
            "account_id": account_id,
            "target_groups": [],
            "error": f"Unexpected error: {str(e)}"
        }


def _find_load_balancer_by_dns(
    elbv2_client,
    dns_name: str
) -> Optional[Dict[str, Any]]:
    """
    Find load balancer by DNS name.
    
    Args:
        elbv2_client: boto3 ELBv2 client
        dns_name: Load balancer DNS name
        
    Returns:
        Load balancer dictionary or None if not found
    """
    try:
        # Normalize dns_name: strip dualstack. prefix
        dns_normalized = dns_name.lower().strip()
        if dns_normalized.startswith('dualstack.'):
            dns_normalized = dns_normalized[len('dualstack.'):]
        
        # List all load balancers
        paginator = elbv2_client.get_paginator('describe_load_balancers')
        
        for page in paginator.paginate():
            for lb in page['LoadBalancers']:
                lb_dns = lb['DNSName'].lower()
                # Match exact, or match without dualstack prefix
                if lb_dns == dns_normalized or lb_dns == dns_name.lower():
                    return lb
                # Also match if dns_name is contained in lb DNS or vice versa
                if dns_normalized in lb_dns or lb_dns in dns_normalized:
                    return lb
        
        return None
        
    except ClientError as e:
        logger.error(f"Error listing load balancers: {e}")
        return None


def _get_target_groups(
    elbv2_client,
    load_balancer_arn: str
) -> List[Dict[str, Any]]:
    """
    Get target groups for a load balancer.
    
    Args:
        elbv2_client: boto3 ELBv2 client
        load_balancer_arn: Load balancer ARN
        
    Returns:
        List of target group dictionaries with health information
    """
    target_groups = []
    
    try:
        # Get target groups for this load balancer
        response = elbv2_client.describe_target_groups(
            LoadBalancerArn=load_balancer_arn
        )
        
        for tg in response['TargetGroups']:
            tg_arn = tg['TargetGroupArn']
            
            # Get target health for this target group
            targets = _get_target_health(elbv2_client, tg_arn)

            target_type = tg.get('TargetType', 'instance')
            target_ips = [t['id'] for t in targets if target_type == 'ip']
            
            target_group_info = {
                "target_group_arn": tg_arn,
                "target_group_name": tg['TargetGroupName'],
                "protocol": tg['Protocol'],
                "port": tg['Port'],
                "vpc_id": tg['VpcId'],
                "health_check_protocol": tg.get('HealthCheckProtocol', 'unknown'),
                "health_check_port": tg.get('HealthCheckPort', 'traffic-port'),
                "health_check_path": tg.get('HealthCheckPath', '/'),
                "target_type": target_type,
                "target_ips": target_ips,
                "targets": targets
            }
            
            target_groups.append(target_group_info)
        
        return target_groups
        
    except ClientError as e:
        logger.error(f"Error getting target groups: {e}")
        return []


def _get_target_health(
    elbv2_client,
    target_group_arn: str
) -> List[Dict[str, Any]]:
    """
    Get target health for a target group.
    
    Args:
        elbv2_client: boto3 ELBv2 client
        target_group_arn: Target group ARN
        
    Returns:
        List of target dictionaries with health status
    """
    targets = []
    
    try:
        response = elbv2_client.describe_target_health(
            TargetGroupArn=target_group_arn
        )
        
        for target_health in response['TargetHealthDescriptions']:
            target = target_health['Target']
            health = target_health['TargetHealth']
            
            target_info = {
                "id": target['Id'],  # IP address or instance ID
                "port": target['Port'],
                "health_status": health['State'],
                "health_reason": health.get('Reason', ''),
                "health_description": health.get('Description', '')
            }
            
            # Add availability zone if present
            if 'AvailabilityZone' in target:
                target_info['availability_zone'] = target['AvailabilityZone']
            
            targets.append(target_info)
        
        return targets
        
    except ClientError as e:
        logger.error(f"Error getting target health: {e}")
        return []


class ELBTool:
    """
    Wrapper class for ELB tool that maintains credential manager reference.
    """
    
    def __init__(self, credential_manager):
        """
        Initialize ELB tool with credential manager.
        
        Args:
            credential_manager: CredentialManager instance
        """
        self.credential_manager = credential_manager
    
    def query_load_balancer(
        self,
        dns_name: Optional[str] = None,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query load balancer details.
        
        Args:
            dns_name: Load balancer DNS name (optional)
            account_id: AWS account ID to search in (optional)
            
        Returns:
            Dictionary with load balancer information
        """
        return query_load_balancer(
            self.credential_manager,
            dns_name=dns_name,
            account_id=account_id
        )


@tool
def describe_load_balancer_listeners(
    credential_manager: Annotated[Any, InjectedToolArg],
    dns_name: Optional[str] = None,
    account_id: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Describe ALB/NLB listeners, rules, and target group targets (IPs when applicable).

    Args:
        dns_name: Load balancer DNS name (required)
        account_id: Optional AWS account ID (defaults to CORE_NETWORK_ACCOUNT_ID)

    Returns:
        JSON with load balancer metadata and listeners[] (rules, actions, target groups, targets)
    """
    try:
        logger.info(f"Describing listeners - DNS: {dns_name}, Account: {account_id}")

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
            import os
            target_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')

        elbv2_client = credential_manager.get_boto3_client(
            'elbv2',
            account_id=target_account
        )

        if not dns_name:
            return {"error": "dns_name must be provided"}

        lb = _find_load_balancer_by_dns(elbv2_client, dns_name)
        if not lb:
            return {"error": f"Load balancer not found for DNS: {dns_name}"}

        lb_arn = lb['LoadBalancerArn']
        listeners = _get_listeners_with_rules(elbv2_client, lb_arn)

        return {
            "load_balancer_arn": lb_arn,
            "load_balancer_name": lb['LoadBalancerName'],
            "dns_name": lb['DNSName'],
            "type": lb['Type'],
            "scheme": lb['Scheme'],
            "vpc_id": lb['VpcId'],
            "account_id": lb_arn.split(':')[4],
            "listeners": listeners
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"ELB API error: {error_code} - {error_message}")
        return {"error": f"ELB API error: {error_code} - {error_message}"}
    except Exception as e:
        logger.error(f"Unexpected error describing listeners: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}


def _get_listeners_with_rules(elbv2_client, load_balancer_arn: str) -> List[Dict[str, Any]]:
    """Return listeners and rules (with forward target group targets/IPs)."""
    listeners_out: List[Dict[str, Any]] = []
    listeners_resp = elbv2_client.describe_listeners(LoadBalancerArn=load_balancer_arn)

    for listener in listeners_resp.get('Listeners', []):
        listener_arn = listener['ListenerArn']

        rules_resp = elbv2_client.describe_rules(ListenerArn=listener_arn)
        rules_out = []

        for rule in rules_resp.get('Rules', []):
            actions = []
            for action in rule.get('Actions', []):
                action_entry = {
                    "type": action.get('Type'),
                    "order": action.get('Order')
                }

                if action.get('Type') == 'forward':
                    tgs = []
                    for tg in action.get('ForwardConfig', {}).get('TargetGroups', []):
                        tg_arn = tg.get('TargetGroupArn')
                        tg_targets = _get_target_health(elbv2_client, tg_arn)
                        tgs.append({
                            "target_group_arn": tg_arn,
                            "weight": tg.get('Weight'),
                            "targets": tg_targets,
                            "target_ips": [t['id'] for t in tg_targets]
                        })
                    action_entry["target_groups"] = tgs

                actions.append(action_entry)

            conditions = []
            for cond in rule.get('Conditions', []):
                cond_entry = {"field": cond.get('Field')}
                if cond.get('HostHeaderConfig'):
                    cond_entry['host_names'] = cond['HostHeaderConfig'].get('Values', [])
                if cond.get('PathPatternConfig'):
                    cond_entry['path_patterns'] = cond['PathPatternConfig'].get('Values', [])
                conditions.append(cond_entry)

            rules_out.append({
                "rule_arn": rule.get('RuleArn'),
                "priority": rule.get('Priority'),
                "is_default": rule.get('IsDefault', False),
                "conditions": conditions,
                "actions": actions
            })

        listeners_out.append({
            "listener_arn": listener_arn,
            "port": listener.get('Port'),
            "protocol": listener.get('Protocol'),
            "ssl_policy": listener.get('SslPolicy'),
            "default_actions": listener.get('DefaultActions', []),
            "rules": rules_out
        })

    return listeners_out
