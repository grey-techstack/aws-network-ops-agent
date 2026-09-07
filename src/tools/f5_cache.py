"""
F5 Load Balancer Cache using DynamoDB.

Caches FQDN → LB mapping to avoid scanning 129+ LBs on every query.
Cache is refreshed daily by EventBridge-triggered Lambda.

DynamoDB Table: aws-ops-agent-f5-cache
  PK: FQDN#{fqdn}  (e.g., FQDN#appcc.example.com)
  SK: LB#{lb_name}  (e.g., LB#lb-app-prd-appcc)
  
  Also stores a full LB index:
  PK: LB_INDEX
  SK: LB#{lb_name}
"""

import json
import logging
import os
import time
import boto3
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

F5_CACHE_TABLE = os.environ.get('F5_CACHE_TABLE', 'aws-ops-agent-f5-cache')
CACHE_TTL_HOURS = int(os.environ.get('F5_CACHE_TTL_HOURS', '48'))


def _get_dynamodb_table():
    """Get DynamoDB table resource."""
    dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'ap-southeast-1'))
    return dynamodb.Table(F5_CACHE_TABLE)


def lookup_fqdn_in_cache(fqdn: str) -> Optional[Dict[str, Any]]:
    """
    Look up FQDN in DynamoDB cache.
    
    Returns:
        Cached LB data if found and not expired, None otherwise.
    """
    try:
        table = _get_dynamodb_table()
        fqdn_normalized = fqdn.lower().rstrip('.')
        
        response = table.query(
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={':pk': f'FQDN#{fqdn_normalized}'}
        )
        
        items = response.get('Items', [])
        if not items:
            return None
        
        item = items[0]
        
        # Check TTL
        cached_at = float(item.get('cached_at', 0))
        age_hours = (time.time() - cached_at) / 3600
        if age_hours > CACHE_TTL_HOURS:
            logger.info(f"Cache expired for {fqdn} (age: {age_hours:.1f}h)")
            return None
        
        logger.info(f"Cache hit for {fqdn} (age: {age_hours:.1f}h)")
        return json.loads(item.get('lb_data', '{}'))
        
    except Exception as e:
        logger.warning(f"Cache lookup failed for {fqdn}: {str(e)}")
        return None


def store_fqdn_mapping(fqdn: str, lb_name: str, lb_data: Dict[str, Any]) -> bool:
    """
    Store FQDN → LB mapping in DynamoDB cache.
    """
    try:
        table = _get_dynamodb_table()
        fqdn_normalized = fqdn.lower().rstrip('.')
        
        table.put_item(Item={
            'pk': f'FQDN#{fqdn_normalized}',
            'sk': f'LB#{lb_name}',
            'fqdn': fqdn_normalized,
            'lb_name': lb_name,
            'lb_data': json.dumps(lb_data, default=str),
            'cached_at': int(time.time()),
            'ttl': int(time.time()) + (CACHE_TTL_HOURS * 3600)
        })
        
        logger.info(f"Cached FQDN mapping: {fqdn} → {lb_name}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to cache FQDN mapping: {str(e)}")
        return False


def store_fqdn_not_found(fqdn: str) -> bool:
    """
    Store negative cache entry (FQDN not found in F5).
    """
    try:
        table = _get_dynamodb_table()
        fqdn_normalized = fqdn.lower().rstrip('.')
        
        table.put_item(Item={
            'pk': f'FQDN#{fqdn_normalized}',
            'sk': 'NOT_FOUND',
            'fqdn': fqdn_normalized,
            'lb_data': json.dumps({'found': False}),
            'cached_at': int(time.time()),
            'ttl': int(time.time()) + (CACHE_TTL_HOURS * 3600)
        })
        
        return True
        
    except Exception as e:
        logger.warning(f"Failed to cache negative result: {str(e)}")
        return False


def bulk_update_cache(fqdn_lb_mappings: List[Dict[str, Any]]) -> int:
    """
    Bulk update cache with FQDN → LB mappings.
    Used by the cache updater Lambda.
    
    Args:
        fqdn_lb_mappings: List of {'fqdn': str, 'lb_name': str, 'lb_data': dict}
    
    Returns:
        Number of items written.
    """
    try:
        table = _get_dynamodb_table()
        count = 0
        
        with table.batch_writer() as batch:
            for mapping in fqdn_lb_mappings:
                fqdn = mapping['fqdn'].lower().rstrip('.')
                lb_name = mapping['lb_name']
                
                batch.put_item(Item={
                    'pk': f'FQDN#{fqdn}',
                    'sk': f'LB#{lb_name}',
                    'fqdn': fqdn,
                    'lb_name': lb_name,
                    'lb_data': json.dumps(mapping.get('lb_data', {}), default=str),
                    'cached_at': int(time.time()),
                    'ttl': int(time.time()) + (CACHE_TTL_HOURS * 3600)
                })
                count += 1
        
        logger.info(f"Bulk cached {count} FQDN mappings")
        return count
        
    except Exception as e:
        logger.error(f"Bulk cache update failed: {str(e)}")
        return 0
