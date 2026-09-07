"""
F5 Distributed Cloud WAF Tool for AWS Operations Agent.

This module provides LangChain tools for querying F5 Distributed Cloud
load balancers, origin pools, and virtual hosts.

Uses InjectedToolArg for credential_manager injection - LLM won't see this parameter.
"""

import os
import json
import requests
import logging
from typing import Dict, Any, Optional, List, Annotated
from langchain_core.tools import tool, InjectedToolArg
from botocore.exceptions import ClientError
from datetime import datetime

logger = logging.getLogger(__name__)


class F5CredentialsManager:
    """Manages F5 API credentials from AWS Secrets Manager."""
    
    def __init__(self, credential_manager, secret_name: str):
        """
        Initialize F5 credentials manager.
        
        Args:
            credential_manager: AWS CredentialManager instance
            secret_name: Name of the secret in Secrets Manager
        """
        self.credential_manager = credential_manager
        self.secret_name = secret_name
        self._credentials_cache = None
    
    def get_credentials(self) -> Dict[str, str]:
        """
        Retrieve F5 API credentials from Secrets Manager.
        
        Returns:
            Dictionary containing:
                - api_url: F5 API base URL
                - api_token: F5 API token
                - namespace: F5 namespace
        """
        if self._credentials_cache is not None:
            return self._credentials_cache
        
        try:
            logger.info(f"Retrieving F5 credentials from secret: {self.secret_name}")
            
            # Get Secrets Manager client
            secrets_client = self.credential_manager.get_boto3_client(
                'secretsmanager',
                account_id=None  # Use current account
            )
            
            response = secrets_client.get_secret_value(SecretId=self.secret_name)
            secret_string = response['SecretString']
            
            # Parse JSON credentials
            credentials = json.loads(secret_string)
            
            # Validate required fields
            required_fields = ['api_url', 'api_token', 'namespace']
            for field in required_fields:
                if field not in credentials:
                    raise ValueError(f"Missing required field in F5 credentials: {field}")
            
            # Cache credentials
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
                raise ValueError(f"Access denied to F5 credentials secret")
            else:
                logger.error(f"Error retrieving F5 credentials: {e}")
                raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in F5 credentials secret: {e}")
            raise ValueError(f"Invalid JSON format in F5 credentials secret")
    
    def get_api_headers(self) -> Dict[str, str]:
        """Get HTTP headers for F5 API requests."""
        credentials = self.get_credentials()
        
        return {
            'Authorization': f'APIToken {credentials["api_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def get_api_url(self, endpoint: str = '') -> str:
        """Get full F5 API URL for a specific endpoint."""
        credentials = self.get_credentials()
        base_url = credentials['api_url'].rstrip('/')
        
        if endpoint:
            endpoint = endpoint.lstrip('/')
            return f"{base_url}/{endpoint}"
        
        return base_url
    
    def get_namespace(self) -> str:
        """Get F5 namespace."""
        credentials = self.get_credentials()
        return credentials['namespace']


def _extract_f5_lb_result(fqdn, lb_name, namespace, metadata, spec):
    """Extract structured result from F5 load balancer detail data."""
    # Extract origin pools
    origin_pools = []
    routes = []
    
    # Get default route origin pools
    default_route_pools = spec.get('default_route_pools', []) or []
    for pool_ref in default_route_pools:
        if pool_ref is None:
            continue
        pool_info = pool_ref.get('pool', {}) or {}
        origin_pools.append({
            'name': pool_info.get('name', 'unknown'),
            'namespace': pool_info.get('namespace', namespace),
            'type': 'default_route'
        })
    
    # Get routes
    for route in (spec.get('routes', []) or []):
        if route is None:
            continue
        simple_route = route.get('simple_route', {}) or {}
        path_obj = simple_route.get('path', {}) or {}
        route_info = {
            'path': path_obj.get('prefix', '/'),
            'origin_pools': []
        }
        for pool_ref in (simple_route.get('origin_pools', []) or []):
            if pool_ref is None:
                continue
            pool_info = pool_ref.get('pool', {}) or {}
            route_info['origin_pools'].append({
                'name': pool_info.get('name', 'unknown'),
                'namespace': pool_info.get('namespace', namespace)
            })
        routes.append(route_info)
    
    # Extract certificate information
    certificate_info = {}
    cert_expiry = spec.get('downstream_tls_certificate_expiration_timestamps', [])
    if cert_expiry:
        certificate_info['expiry_dates'] = cert_expiry
        if len(cert_expiry) > 0:
            try:
                expiry_dt = datetime.fromisoformat(cert_expiry[0].replace('Z', '+00:00'))
                certificate_info['expiry_date'] = expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                days_until_expiry = (expiry_dt - datetime.now(expiry_dt.tzinfo)).days
                certificate_info['days_until_expiry'] = days_until_expiry
            except Exception as e:
                logger.warning(f"Failed to parse certificate expiry date: {e}")
                certificate_info['expiry_date'] = cert_expiry[0]
    
    https_config = spec.get('https', {})
    if https_config:
        certificate_info['http_redirect'] = https_config.get('http_redirect', False)
        certificate_info['port'] = https_config.get('port', 443)
        tls_cert_params = https_config.get('tls_cert_params', {})
        if tls_cert_params:
            certs = tls_cert_params.get('certificates', [])
            certificate_info['certificates'] = []
            for cert in certs:
                certificate_info['certificates'].append({
                    'name': cert.get('name', 'unknown'),
                    'namespace': cert.get('namespace', namespace)
                })
            tls_config = tls_cert_params.get('tls_config', {})
            if 'default_security' in tls_config:
                certificate_info['tls_security'] = 'default'
            elif 'custom_security' in tls_config:
                certificate_info['tls_security'] = 'custom'
    
    certificate_info['state'] = spec.get('cert_state', 'Unknown')
    
    # Service policies
    service_policies = []
    active_policies_obj = spec.get('active_service_policies', {}) or {}
    for policy in (active_policies_obj.get('policies', []) or []):
        if policy is None:
            continue
        service_policies.append({
            'name': policy.get('name', 'unknown'),
            'namespace': policy.get('namespace', namespace)
        })
    
    # App firewall
    app_firewall = spec.get('app_firewall', {})
    app_firewall_name = app_firewall.get('name', None) if app_firewall else None
    
    # Trusted clients
    trusted_clients = []
    for client in (spec.get('trusted_clients', []) or []):
        if client is None:
            continue
        client_metadata = client.get('metadata', {}) or {}
        trusted_clients.append({
            'ip_prefix': client.get('ip_prefix', 'unknown'),
            'actions': client.get('actions', []),
            'description': client_metadata.get('description', '')
        })
    
    domains = spec.get('domains', []) or []
    
    return {
        "found": True,
        "fqdn": fqdn,
        "load_balancer_name": lb_name,
        "namespace": namespace,
        "description": (metadata or {}).get('description', ''),
        "labels": (metadata or {}).get('labels', {}),
        "state": spec.get('state', 'Unknown'),
        "domains": domains,
        "certificate": certificate_info,
        "origin_pools": origin_pools,
        "routes": routes,
        "service_policies": service_policies,
        "app_firewall": app_firewall_name,
        "trusted_clients": trusted_clients
    }


@tool
def query_f5_load_balancer(
    fqdn: str,
    credential_manager: Annotated[Any, InjectedToolArg],
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query F5 Distributed Cloud load balancer configuration for an FQDN.
    Use this tool to find F5 WAF/load balancer details for a domain.
    
    Args:
        fqdn: Fully qualified domain name (e.g., demo.example.com)
        
    Returns:
        JSON with load balancer details, domains, origin pools, and routes
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info(f"Querying F5 load balancer for FQDN: {fqdn}")
        
        # --- CHECK CACHE FIRST ---
        try:
            from src.tools.f5_cache import lookup_fqdn_in_cache, store_fqdn_mapping, store_fqdn_not_found
            
            cached = lookup_fqdn_in_cache(fqdn)
            if cached is not None:
                execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                cloudwatch_logger.log_tool_execution(
                    tool_name='query_f5_load_balancer',
                    parameters={'fqdn': fqdn},
                    execution_time_ms=execution_time_ms,
                    success=True,
                    request_id=request_id,
                    result_summary=f"Cache hit: {cached.get('load_balancer_name', 'not found')}"
                )
                if not cached.get('found', False):
                    logger.info(f"Cache hit (negative): no F5 LB for {fqdn}")
                    return {
                        "found": False,
                        "fqdn": fqdn,
                        "message": f"No F5 load balancer found for FQDN: {fqdn} (cached)",
                        "total_load_balancers_checked": 0
                    }
                logger.info(f"Cache hit: {fqdn} → {cached.get('load_balancer_name')}")
                return cached
        except ImportError:
            logger.debug("F5 cache module not available, using live API")
        except Exception as e:
            logger.warning(f"Cache lookup failed, falling back to live API: {str(e)}")
        
        # --- LIVE API FALLBACK ---
        
        # Get F5 secret name from environment
        f5_secret_name = os.environ.get('F5_SECRET_NAME')
        if not f5_secret_name:
            raise ValueError("F5_SECRET_NAME environment variable not set")
        
        # Initialize F5 credentials manager
        f5_creds = F5CredentialsManager(credential_manager, f5_secret_name)
        
        # Get credentials
        headers = f5_creds.get_api_headers()
        namespace = f5_creds.get_namespace()
        
        # Query HTTP load balancers
        endpoint = f"config/namespaces/{namespace}/http_loadbalancers"
        url = f5_creds.get_api_url(endpoint)
        
        logger.info(f"Making F5 API call to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle None or empty response
        if data is None:
            logger.warning("F5 API returned None response")
            return {
                "found": False,
                "fqdn": fqdn,
                "message": "F5 API returned None response",
                "total_load_balancers_checked": 0
            }
        
        if not data:
            logger.warning("F5 API returned empty response")
            return {
                "found": False,
                "fqdn": fqdn,
                "message": "F5 API returned empty response",
                "total_load_balancers_checked": 0
            }
        
        items = data.get('items', [])
        if items is None:
            items = []
        
        # Normalize FQDN for comparison
        fqdn_normalized = fqdn.lower().rstrip('.')
        
        logger.info(f"Searching for FQDN: {fqdn} (normalized: {fqdn_normalized})")
        logger.info(f"Total load balancers to check: {len(items)}")
        
        # --- OPTIMIZATION: Pre-filter LB names using FQDN parts ---
        # Extract meaningful parts from FQDN for name-based pre-filtering
        # e.g., "app-hk-uat.example.com" → ["app-hk-uat", "apihk", "uat"]
        fqdn_parts = fqdn_normalized.split('.')
        hostname = fqdn_parts[0] if fqdn_parts else ''  # e.g., "app-hk-uat"
        hostname_segments = hostname.split('-')  # e.g., ["uat", "apihk"]
        
        # Build search keywords from hostname
        search_keywords = set()
        search_keywords.add(hostname)  # full hostname
        for seg in hostname_segments:
            if len(seg) >= 3:  # skip very short segments like "a", "to"
                search_keywords.add(seg)
        
        logger.info(f"Pre-filter keywords: {search_keywords}")
        
        # Separate LBs into priority (name matches keyword) and remaining
        priority_lbs = []
        remaining_lbs = []
        for lb in items:
            if lb is None:
                continue
            lb_name = lb.get('name', 'unknown').lower()
            if any(kw in lb_name for kw in search_keywords):
                priority_lbs.append(lb)
            else:
                remaining_lbs.append(lb)
        
        logger.info(f"Pre-filter: {len(priority_lbs)} priority LBs, {len(remaining_lbs)} remaining")
        
        # --- OPTIMIZATION: Use concurrent requests with timeout guard ---
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        TIMEOUT_SECONDS = 90  # Leave buffer for Lambda 160s timeout
        
        def fetch_lb_detail(lb_item):
            """Fetch full LB details from F5 API. Returns (lb_item, detail_data) or (lb_item, None)."""
            lb_name = lb_item.get('name', 'unknown')
            lb_namespace = lb_item.get('namespace', namespace)
            try:
                detail_endpoint = f"config/namespaces/{lb_namespace}/http_loadbalancers/{lb_name}"
                detail_url = f5_creds.get_api_url(detail_endpoint)
                detail_response = requests.get(detail_url, headers=headers, timeout=10)
                detail_response.raise_for_status()
                return (lb_item, detail_response.json())
            except Exception as e:
                logger.warning(f"Failed to get details for LB {lb_name}: {e}")
                return (lb_item, None)
        
        def check_lb_match(lb_item, detail_data):
            """Check if LB detail data matches our FQDN. Returns extracted result or None."""
            if detail_data is None:
                return None
            
            metadata = detail_data.get('metadata', {}) or {}
            spec = detail_data.get('spec', {}) or {}
            domains = spec.get('domains', []) or []
            
            for domain in domains:
                domain_norm = domain.lower().rstrip('.')
                if domain_norm == fqdn_normalized:
                    return _extract_f5_lb_result(
                        fqdn, lb_item.get('name', 'unknown'),
                        namespace, metadata, spec
                    )
            return None
        
        def search_batch(lb_batch, max_workers=8):
            """Search a batch of LBs concurrently. Returns result if found, else None."""
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(fetch_lb_detail, lb): lb for lb in lb_batch}
                for future in as_completed(futures):
                    # Check timeout
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    if elapsed > TIMEOUT_SECONDS:
                        logger.warning(f"Timeout guard: {elapsed:.1f}s elapsed, stopping search")
                        executor.shutdown(wait=False, cancel_futures=True)
                        return 'TIMEOUT'
                    
                    lb_item, detail_data = future.result()
                    match = check_lb_match(lb_item, detail_data)
                    if match is not None:
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        return match
            return None
        
        # Search priority LBs first (likely matches)
        if priority_lbs:
            result = search_batch(priority_lbs, max_workers=8)
            if result == 'TIMEOUT':
                return {
                    "found": False,
                    "fqdn": fqdn,
                    "error": f"Search timed out after {TIMEOUT_SECONDS}s. Checked {len(priority_lbs)} priority LBs out of {len(items)} total.",
                    "total_load_balancers_checked": len(priority_lbs)
                }
            if result is not None:
                execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                cloudwatch_logger.log_tool_execution(
                    tool_name='query_f5_load_balancer',
                    parameters={'fqdn': fqdn},
                    execution_time_ms=execution_time_ms,
                    success=True,
                    request_id=request_id,
                    result_summary=f"Found load balancer: {result.get('load_balancer_name', 'unknown')} (priority match)"
                )
                # Cache the result
                try:
                    store_fqdn_mapping(fqdn, result.get('load_balancer_name', ''), result)
                except Exception:
                    pass
                return result
        
        # Search remaining LBs if not found in priority batch
        if remaining_lbs:
            result = search_batch(remaining_lbs, max_workers=10)
            if result == 'TIMEOUT':
                checked = len(priority_lbs) + len(remaining_lbs)
                return {
                    "found": False,
                    "fqdn": fqdn,
                    "error": f"Search timed out after {TIMEOUT_SECONDS}s. Checked priority LBs but timed out on remaining.",
                    "total_load_balancers_checked": checked
                }
            if result is not None:
                execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                cloudwatch_logger.log_tool_execution(
                    tool_name='query_f5_load_balancer',
                    parameters={'fqdn': fqdn},
                    execution_time_ms=execution_time_ms,
                    success=True,
                    request_id=request_id,
                    result_summary=f"Found load balancer: {result.get('load_balancer_name', 'unknown')}"
                )
                # Cache the result
                try:
                    store_fqdn_mapping(fqdn, result.get('load_balancer_name', ''), result)
                except Exception:
                    pass
                return result
        
        # No matching load balancer found — cache negative result
        try:
            store_fqdn_not_found(fqdn)
        except Exception:
            pass
        
        result = {
            "found": False,
            "fqdn": fqdn,
            "message": f"No F5 load balancer found for FQDN: {fqdn}",
            "total_load_balancers_checked": len(items)
        }
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='query_f5_load_balancer',
            parameters={'fqdn': fqdn},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary="No matching load balancer found"
        )
        
        logger.info(f"No F5 load balancer found for {fqdn}")
        return result
        
    except requests.exceptions.RequestException as e:
        error_message = f"F5 API request failed: {str(e)}"
        logger.error(error_message)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_load_balancer',
                parameters={'fqdn': fqdn},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "found": False,
            "fqdn": fqdn,
            "error": error_message
        }
    
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(f"Error querying F5 load balancer: {error_message}")
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_load_balancer',
                parameters={'fqdn': fqdn},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "found": False,
            "fqdn": fqdn,
            "error": error_message
        }


@tool
def query_f5_origin_pool(
    pool_name: str,
    credential_manager: Annotated[Any, InjectedToolArg],
    namespace: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query F5 Distributed Cloud origin pool details.
    Use this tool to get backend server/endpoint details for an F5 origin pool.
    
    Args:
        pool_name: Name of the origin pool
        namespace: F5 namespace (optional, uses default from credentials)
        
    Returns:
        JSON with origin pool details including origin servers, port, and health check config
    
    NEXT STEP - Based on the origin server address, auto-chain to the correct tool:
    - If origin server is *.elb.amazonaws.com → use query_load_balancer / describe_load_balancer_listeners
    - If origin server is *.cloudfront.net → use query_cloudfront_distribution
    - If origin server is ves-io-*.ac.vh.ves.io → use query_f5_load_balancer / query_f5_origin_pool
    - Otherwise → use execute_aws_cli_command to investigate
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info(f"Querying F5 origin pool: {pool_name}")
        
        # Get F5 secret name from environment
        f5_secret_name = os.environ.get('F5_SECRET_NAME')
        if not f5_secret_name:
            raise ValueError("F5_SECRET_NAME environment variable not set")
        
        # Initialize F5 credentials manager
        f5_creds = F5CredentialsManager(credential_manager, f5_secret_name)
        
        # Get credentials
        headers = f5_creds.get_api_headers()
        target_namespace = namespace or f5_creds.get_namespace()
        
        # Query specific origin pool
        endpoint = f"config/namespaces/{target_namespace}/origin_pools/{pool_name}"
        url = f5_creds.get_api_url(endpoint)
        
        logger.info(f"Making F5 API call to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            result = {
                "found": False,
                "pool_name": pool_name,
                "namespace": target_namespace,
                "message": f"Origin pool not found: {pool_name}"
            }
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_origin_pool',
                parameters={'pool_name': pool_name, 'namespace': target_namespace},
                execution_time_ms=execution_time_ms,
                success=True,
                request_id=request_id,
                result_summary="Origin pool not found"
            )
            
            return result
        
        response.raise_for_status()
        data = response.json()
        
        spec = data.get('spec', {})
        
        # Extract origin servers
        origin_servers = []
        for origin in spec.get('origin_servers', []):
            server_info = {}
            
            # Handle different origin server types
            if 'public_name' in origin:
                server_info = {
                    'type': 'public_name',
                    'dns_name': origin['public_name'].get('dns_name', 'unknown')
                }
            elif 'public_ip' in origin:
                server_info = {
                    'type': 'public_ip',
                    'ip': origin['public_ip'].get('ip', 'unknown')
                }
            elif 'private_name' in origin:
                server_info = {
                    'type': 'private_name',
                    'dns_name': origin['private_name'].get('dns_name', 'unknown'),
                    'site_locator': origin['private_name'].get('site_locator', {})
                }
            elif 'private_ip' in origin:
                server_info = {
                    'type': 'private_ip',
                    'ip': origin['private_ip'].get('ip', 'unknown'),
                    'site_locator': origin['private_ip'].get('site_locator', {})
                }
            elif 'k8s_service' in origin:
                server_info = {
                    'type': 'k8s_service',
                    'service_name': origin['k8s_service'].get('service_name', 'unknown'),
                    'site_locator': origin['k8s_service'].get('site_locator', {})
                }
            
            origin_servers.append(server_info)
        
        # Extract port
        port = spec.get('port', 80)
        
        # Extract health check configuration
        health_check = {}
        if 'health_check' in spec:
            hc = spec['health_check'][0] if isinstance(spec['health_check'], list) else spec['health_check']
            health_check = {
                'path': hc.get('path', '/'),
                'interval': hc.get('interval', 30),
                'timeout': hc.get('timeout', 3),
                'unhealthy_threshold': hc.get('unhealthy_threshold', 3),
                'healthy_threshold': hc.get('healthy_threshold', 3)
            }
        
        result = {
            "found": True,
            "pool_name": pool_name,
            "namespace": target_namespace,
            "origin_servers": origin_servers,
            "port": port,
            "health_check": health_check,
            "loadbalancer_algorithm": spec.get('loadbalancer_algorithm', 'ROUND_ROBIN')
        }
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='query_f5_origin_pool',
            parameters={'pool_name': pool_name, 'namespace': target_namespace},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found {len(origin_servers)} origin servers"
        )
        
        logger.info(f"Found F5 origin pool: {pool_name} with {len(origin_servers)} servers")
        return result
        
    except requests.exceptions.RequestException as e:
        error_message = f"F5 API request failed: {str(e)}"
        logger.error(error_message)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_origin_pool',
                parameters={'pool_name': pool_name},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "found": False,
            "pool_name": pool_name,
            "error": error_message
        }
    
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(f"Error querying F5 origin pool: {error_message}")
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_origin_pool',
                parameters={'pool_name': pool_name},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "found": False,
            "pool_name": pool_name,
            "error": error_message
        }


@tool
def list_f5_load_balancers(
    credential_manager: Annotated[Any, InjectedToolArg],
    namespace: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    List all F5 Distributed Cloud HTTP load balancers in a namespace.
    Use this tool to discover all F5 load balancers.
    
    Args:
        namespace: F5 namespace (optional, uses default from credentials)
        
    Returns:
        JSON with list of load balancer summaries including names, domains, and counts
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info("Listing F5 load balancers")
        
        # Get F5 secret name from environment
        f5_secret_name = os.environ.get('F5_SECRET_NAME')
        if not f5_secret_name:
            raise ValueError("F5_SECRET_NAME environment variable not set")
        
        # Initialize F5 credentials manager
        f5_creds = F5CredentialsManager(credential_manager, f5_secret_name)
        
        # Get credentials
        headers = f5_creds.get_api_headers()
        target_namespace = namespace or f5_creds.get_namespace()
        
        # Query HTTP load balancers
        endpoint = f"config/namespaces/{target_namespace}/http_loadbalancers"
        url = f5_creds.get_api_url(endpoint)
        
        logger.info(f"Making F5 API call to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            logger.warning("F5 API returned empty response")
            return {
                "namespace": target_namespace,
                "load_balancers": [],
                "count": 0
            }
        
        items = data.get('items', [])
        if items is None:
            items = []
        
        logger.info(f"Found {len(items)} load balancers in namespace {target_namespace}")
        
        # Extract load balancer summaries
        # Note: List API returns simplified structure without full spec
        load_balancers = []
        for lb in items:
            try:
                # List API structure: name, namespace, description at top level
                # No metadata or spec in list response
                if not lb:
                    continue
                
                lb_name = lb.get('name', 'unknown')
                lb_namespace = lb.get('namespace', target_namespace)
                lb_description = lb.get('description', '')
                
                # For list API, we don't have full spec data
                # User needs to query individual load balancer for full details
                lb_summary = {
                    'name': lb_name,
                    'namespace': lb_namespace,
                    'description': lb_description
                }
                
                load_balancers.append(lb_summary)
            except Exception as e:
                logger.error(f"Error processing load balancer: {e}", exc_info=True)
                # Continue with next load balancer
                continue
        
        result = {
            "namespace": target_namespace,
            "load_balancers": load_balancers,
            "count": len(load_balancers)
        }
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_f5_load_balancers',
            parameters={'namespace': target_namespace},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found {len(load_balancers)} load balancers"
        )
        
        logger.info(f"Found {len(load_balancers)} F5 load balancers")
        return result
        
    except requests.exceptions.RequestException as e:
        error_message = f"F5 API request failed: {str(e)}"
        logger.error(error_message)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='list_f5_load_balancers',
                parameters={'namespace': namespace},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "namespace": namespace,
            "load_balancers": [],
            "count": 0,
            "error": error_message
        }
    
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(f"Error listing F5 load balancers: {error_message}")
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='list_f5_load_balancers',
                parameters={'namespace': namespace},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "namespace": namespace,
            "load_balancers": [],
            "count": 0,
            "error": error_message
        }


@tool
def query_f5_load_balancer_by_name(
    lb_name: str,
    credential_manager: Annotated[Any, InjectedToolArg],
    namespace: Optional[str] = None,
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    Query F5 Distributed Cloud load balancer by name.
    Use this tool to get full details of a specific F5 load balancer when you know its name.
    
    Args:
        lb_name: Load balancer name (e.g., lb-app-dev-app-svc)
        namespace: F5 namespace (optional, uses default from credentials)
        
    Returns:
        JSON with full load balancer details including domains, certificates, origin pools, routes
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info(f"Querying F5 load balancer by name: {lb_name}")
        
        # Get F5 secret name from environment
        f5_secret_name = os.environ.get('F5_SECRET_NAME')
        if not f5_secret_name:
            raise ValueError("F5_SECRET_NAME environment variable not set")
        
        # Initialize F5 credentials manager
        f5_creds = F5CredentialsManager(credential_manager, f5_secret_name)
        
        # Get credentials
        headers = f5_creds.get_api_headers()
        target_namespace = namespace or f5_creds.get_namespace()
        
        # Query specific load balancer
        endpoint = f"config/namespaces/{target_namespace}/http_loadbalancers/{lb_name}"
        url = f5_creds.get_api_url(endpoint)
        
        logger.info(f"Making F5 API call to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            result = {
                "found": False,
                "load_balancer_name": lb_name,
                "namespace": target_namespace,
                "message": f"Load balancer not found: {lb_name}"
            }
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_load_balancer_by_name',
                parameters={'lb_name': lb_name, 'namespace': target_namespace},
                execution_time_ms=execution_time_ms,
                success=True,
                request_id=request_id,
                result_summary="Load balancer not found"
            )
            
            return result
        
        response.raise_for_status()
        data = response.json()
        
        # Extract from full response structure
        metadata = data.get('metadata', {})
        spec = data.get('spec', {})
        
        # Extract certificate information
        certificate_info = {}
        cert_expiry = spec.get('downstream_tls_certificate_expiration_timestamps', [])
        if cert_expiry:
            certificate_info['expiry_dates'] = cert_expiry
            if len(cert_expiry) > 0:
                try:
                    expiry_dt = datetime.fromisoformat(cert_expiry[0].replace('Z', '+00:00'))
                    certificate_info['expiry_date'] = expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                    days_until_expiry = (expiry_dt - datetime.now(expiry_dt.tzinfo)).days
                    certificate_info['days_until_expiry'] = days_until_expiry
                except Exception as e:
                    logger.warning(f"Failed to parse certificate expiry date: {e}")
                    certificate_info['expiry_date'] = cert_expiry[0]
        
        # Get HTTPS configuration
        https_config = spec.get('https', {})
        if https_config:
            certificate_info['http_redirect'] = https_config.get('http_redirect', False)
            certificate_info['port'] = https_config.get('port', 443)
            
            tls_cert_params = https_config.get('tls_cert_params', {})
            if tls_cert_params:
                certs = tls_cert_params.get('certificates', [])
                certificate_info['certificates'] = []
                for cert in certs:
                    certificate_info['certificates'].append({
                        'name': cert.get('name', 'unknown'),
                        'namespace': cert.get('namespace', target_namespace)
                    })
                
                tls_config = tls_cert_params.get('tls_config', {})
                if 'default_security' in tls_config:
                    certificate_info['tls_security'] = 'default'
                elif 'custom_security' in tls_config:
                    certificate_info['tls_security'] = 'custom'
        
        certificate_info['state'] = spec.get('cert_state', 'Unknown')
        
        # Extract origin pools
        origin_pools = []
        default_route_pools = spec.get('default_route_pools', [])
        if default_route_pools is None:
            default_route_pools = []
        for pool_ref in default_route_pools:
            if pool_ref is None:
                continue
            pool_info = pool_ref.get('pool', {})
            if pool_info is None:
                pool_info = {}
            origin_pools.append({
                'name': pool_info.get('name', 'unknown'),
                'namespace': pool_info.get('namespace', target_namespace),
                'type': 'default_route'
            })
        
        # Extract routes
        routes = []
        for route in spec.get('routes', []):
            if route is None:
                continue
            
            simple_route = route.get('simple_route', {})
            if simple_route is None:
                simple_route = {}
            
            path_obj = simple_route.get('path', {})
            if path_obj is None:
                path_obj = {}
            
            route_info = {
                'path': path_obj.get('prefix', '/'),
                'origin_pools': []
            }
            
            route_origin_pools = simple_route.get('origin_pools', [])
            if route_origin_pools is None:
                route_origin_pools = []
            
            for pool_ref in route_origin_pools:
                if pool_ref is None:
                    continue
                pool_info = pool_ref.get('pool', {})
                if pool_info is None:
                    pool_info = {}
                route_info['origin_pools'].append({
                    'name': pool_info.get('name', 'unknown'),
                    'namespace': pool_info.get('namespace', target_namespace)
                })
            routes.append(route_info)
        
        # Get service policies
        service_policies = []
        active_policies_obj = spec.get('active_service_policies', {})
        if active_policies_obj is None:
            active_policies_obj = {}
        active_policies = active_policies_obj.get('policies', [])
        if active_policies is None:
            active_policies = []
        for policy in active_policies:
            if policy is None:
                continue
            service_policies.append({
                'name': policy.get('name', 'unknown'),
                'namespace': policy.get('namespace', target_namespace)
            })
        
        # Get app firewall
        app_firewall = spec.get('app_firewall', {})
        app_firewall_name = app_firewall.get('name', None) if app_firewall else None
        
        # Get trusted clients
        trusted_clients = []
        for client in spec.get('trusted_clients', []):
            if client is None:
                continue
            client_metadata = client.get('metadata', {})
            if client_metadata is None:
                client_metadata = {}
            trusted_clients.append({
                'ip_prefix': client.get('ip_prefix', 'unknown'),
                'actions': client.get('actions', []),
                'description': client_metadata.get('description', '')
            })
        
        result = {
            "found": True,
            "load_balancer_name": lb_name,
            "namespace": target_namespace,
            "description": metadata.get('description', ''),
            "labels": metadata.get('labels', {}),
            "state": spec.get('state', 'Unknown'),
            "domains": spec.get('domains', []),
            "certificate": certificate_info,
            "origin_pools": origin_pools,
            "routes": routes,
            "service_policies": service_policies,
            "app_firewall": app_firewall_name,
            "trusted_clients": trusted_clients
        }
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='query_f5_load_balancer_by_name',
            parameters={'lb_name': lb_name, 'namespace': target_namespace},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found load balancer with {len(spec.get('domains', []))} domains"
        )
        
        logger.info(f"Found F5 load balancer: {lb_name}")
        return result
        
    except requests.exceptions.RequestException as e:
        error_message = f"F5 API request failed: {str(e)}"
        logger.error(error_message)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_load_balancer_by_name',
                parameters={'lb_name': lb_name},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "found": False,
            "load_balancer_name": lb_name,
            "error": error_message
        }
    
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(f"Error querying F5 load balancer by name: {error_message}")
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='query_f5_load_balancer_by_name',
                parameters={'lb_name': lb_name},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "found": False,
            "load_balancer_name": lb_name,
            "error": error_message
        }


@tool
def list_f5_namespaces(
    credential_manager: Annotated[Any, InjectedToolArg],
    request_id: Annotated[str, InjectedToolArg] = 'unknown'
) -> Dict[str, Any]:
    """
    List all F5 Distributed Cloud namespaces.
    Use this tool to discover all available F5 namespaces.
        
    Returns:
        JSON with list of namespace names and count
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info("Listing F5 namespaces")
        
        # Get F5 secret name from environment
        f5_secret_name = os.environ.get('F5_SECRET_NAME')
        if not f5_secret_name:
            raise ValueError("F5_SECRET_NAME environment variable not set")
        
        # Initialize F5 credentials manager
        f5_creds = F5CredentialsManager(credential_manager, f5_secret_name)
        
        # Get credentials
        headers = f5_creds.get_api_headers()
        
        # Query namespaces
        endpoint = "web/namespaces"
        url = f5_creds.get_api_url(endpoint)
        
        logger.info(f"Making F5 API call to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract namespace names
        namespaces = []
        for ns in data.get('items', []):
            ns_name = ns.get('name', 'unknown')
            namespaces.append(ns_name)
        
        result = {
            "namespaces": namespaces,
            "count": len(namespaces)
        }
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        cloudwatch_logger.log_tool_execution(
            tool_name='list_f5_namespaces',
            parameters={},
            execution_time_ms=execution_time_ms,
            success=True,
            request_id=request_id,
            result_summary=f"Found {len(namespaces)} namespaces"
        )
        
        logger.info(f"Found {len(namespaces)} F5 namespaces")
        return result
        
    except requests.exceptions.RequestException as e:
        error_message = f"F5 API request failed: {str(e)}"
        logger.error(error_message)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='list_f5_namespaces',
                parameters={},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "namespaces": [],
            "count": 0,
            "error": error_message
        }
    
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(f"Error listing F5 namespaces: {error_message}")
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='list_f5_namespaces',
                parameters={},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            pass
        
        return {
            "namespaces": [],
            "count": 0,
            "error": error_message
        }


class F5WAFTool:
    """
    Wrapper class for F5 WAF tools that maintains credential manager reference.
    """
    
    def __init__(self, credential_manager):
        """Initialize F5 WAF tool with credential manager."""
        self.credential_manager = credential_manager
    
    def query_load_balancer(self, fqdn: str) -> Dict[str, Any]:
        """Query F5 load balancer for an FQDN."""
        return query_f5_load_balancer(fqdn, self.credential_manager)
    
    def query_origin_pool(self, pool_name: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Query F5 origin pool details."""
        return query_f5_origin_pool(pool_name, self.credential_manager, namespace)
    
    def list_load_balancers(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """List all F5 load balancers."""
        return list_f5_load_balancers(self.credential_manager, namespace)
