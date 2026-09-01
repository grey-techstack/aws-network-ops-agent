"""
F5 Cache Updater Lambda.

Triggered by EventBridge daily.
Fetches all F5 load balancers, extracts FQDN→LB mappings, and stores in DynamoDB.
"""

import json
import logging
import os
import boto3
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """EventBridge scheduled handler to refresh F5 cache."""
    logger.info("F5 cache updater started")
    start_time = datetime.utcnow()
    
    try:
        # Get F5 credentials from Secrets Manager
        f5_secret_name = os.environ.get('F5_SECRET_NAME', 'f5-distributed-cloud-api-credentials')
        region = os.environ.get('AWS_REGION', 'ap-southeast-1')
        
        secrets_client = boto3.client('secretsmanager', region_name=region)
        secret_response = secrets_client.get_secret_value(SecretId=f5_secret_name)
        secret = json.loads(secret_response['SecretString'])
        
        api_token = secret.get('api_token')
        tenant_url = secret.get('tenant_url', 'https://example.console.example.io')
        namespace = secret.get('namespace', 'acme-net')
        
        headers = {
            'Authorization': f'APIToken {api_token}',
            'Content-Type': 'application/json'
        }
        
        # Step 1: Get all namespaces
        ns_url = f"{tenant_url}/api/web/namespaces"
        logger.info(f"Fetching namespaces from: {ns_url}")
        
        ns_response = requests.get(ns_url, headers=headers, timeout=30)
        ns_response.raise_for_status()
        all_namespaces = [ns.get('name') for ns in ns_response.json().get('items', []) if ns.get('name')]
        
        # Filter to namespaces that likely have HTTP LBs (skip system namespaces)
        skip_ns = {'shared', 'system', 'default', 'ves-io-shared'}
        namespaces_to_scan = [ns for ns in all_namespaces if ns not in skip_ns]
        logger.info(f"Found {len(all_namespaces)} namespaces, scanning {len(namespaces_to_scan)}")
        
        # Step 2: Get all LBs from all namespaces
        all_items = []
        for ns in namespaces_to_scan:
            try:
                list_url = f"{tenant_url}/api/config/namespaces/{ns}/http_loadbalancers"
                response = requests.get(list_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    items = response.json().get('items', [])
                    for item in items:
                        item['_namespace'] = ns  # tag with namespace
                    all_items.extend(items)
                    if items:
                        logger.info(f"  Namespace {ns}: {len(items)} LBs")
            except Exception as e:
                logger.warning(f"  Failed to scan namespace {ns}: {e}")
                continue
        
        logger.info(f"Total load balancers across all namespaces: {len(all_items)}")
        items = all_items
        
        logger.info(f"Found {len(items)} load balancers")
        
        # Step 2: Fetch details for each LB concurrently
        def fetch_lb_detail(lb_item):
            lb_name = lb_item.get('name', 'unknown')
            lb_ns = lb_item.get('_namespace', lb_item.get('namespace', 'acme-net'))
            try:
                detail_url = f"{tenant_url}/api/config/namespaces/{lb_ns}/http_loadbalancers/{lb_name}"
                detail_resp = requests.get(detail_url, headers=headers, timeout=10)
                detail_resp.raise_for_status()
                return detail_resp.json()
            except Exception as e:
                logger.warning(f"Failed to fetch LB {lb_name}: {e}")
                return None
        
        fqdn_mappings = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_lb_detail, lb): lb for lb in items}
            
            for future in as_completed(futures):
                detail = future.result()
                if detail is None:
                    continue
                
                metadata = detail.get('metadata', {}) or {}
                spec = detail.get('spec', {}) or {}
                lb_name = metadata.get('name', 'unknown')
                lb_ns = detail.get('metadata', {}).get('namespace', 'unknown')
                domains = spec.get('domains', []) or []
                
                # Extract certificate info
                cert_info = {}
                cert_expiry = spec.get('downstream_tls_certificate_expiration_timestamps', [])
                if cert_expiry:
                    try:
                        expiry_dt = datetime.fromisoformat(cert_expiry[0].replace('Z', '+00:00'))
                        cert_info['expiry_date'] = expiry_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                        cert_info['days_until_expiry'] = (expiry_dt - datetime.now(expiry_dt.tzinfo)).days
                    except Exception:
                        cert_info['expiry_date'] = cert_expiry[0] if cert_expiry else None
                
                # Extract origin pools
                origin_pools = []
                for pool_ref in (spec.get('default_route_pools', []) or []):
                    if pool_ref is None:
                        continue
                    pool_info = pool_ref.get('pool', {}) or {}
                    origin_pools.append({
                        'name': pool_info.get('name', 'unknown'),
                        'namespace': pool_info.get('namespace', lb_ns)
                    })
                
                # Build LB data
                lb_data = {
                    'found': True,
                    'load_balancer_name': lb_name,
                    'namespace': lb_ns,
                    'domains': domains,
                    'certificate': cert_info,
                    'origin_pools': origin_pools,
                    'waf_enabled': spec.get('app_firewall', {}).get('name') is not None if spec.get('app_firewall') else False
                }
                
                # Create mapping for each domain
                for domain in domains:
                    fqdn_mappings.append({
                        'fqdn': domain,
                        'lb_name': lb_name,
                        'lb_data': lb_data
                    })
        
        # Step 3: Bulk write to DynamoDB
        from src.tools.f5_cache import bulk_update_cache
        count = bulk_update_cache(fqdn_mappings)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        result = {
            'success': True,
            'total_lbs': len(items),
            'total_fqdn_mappings': len(fqdn_mappings),
            'cached_count': count,
            'elapsed_seconds': round(elapsed, 1)
        }
        
        logger.info(f"F5 cache update complete: {json.dumps(result)}")
        return result
        
    except Exception as e:
        logger.error(f"F5 cache update failed: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
