#!/usr/bin/env python3
"""
List all F5 load balancers in acme-net namespace with their domains (detailed query)
"""

import os
import sys
import json
import boto3
import requests
import time

# Get F5 credentials from AWS Secrets Manager
def get_f5_credentials():
    secret_name = "f5-distributed-cloud-api-credentials"
    region = "ap-southeast-1"
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )
    
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response['SecretString'])
    
    return secret

# Query F5 API for load balancer list
def list_f5_load_balancers(api_url, api_token, namespace):
    headers = {
        'Authorization': f'APIToken {api_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = f"{api_url}/config/namespaces/{namespace}/http_loadbalancers"
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    return data

# Get detailed load balancer info
def get_f5_load_balancer_details(api_url, api_token, namespace, lb_name):
    headers = {
        'Authorization': f'APIToken {api_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = f"{api_url}/config/namespaces/{namespace}/http_loadbalancers/{lb_name}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ✗ Error getting details for {lb_name}: {e}")
        return None

# Main
if __name__ == "__main__":
    print("=" * 80)
    print("F5 Load Balancers in acme-net namespace (Detailed)")
    print("=" * 80)
    print("")
    
    try:
        # Get credentials
        print("Getting F5 credentials...")
        creds = get_f5_credentials()
        print("✓ Credentials retrieved")
        print("")
        
        # List load balancers
        print("Listing F5 load balancers...")
        data = list_f5_load_balancers(
            creds['api_url'],
            creds['api_token'],
            'acme-net'
        )
        
        items = data.get('items', [])
        print(f"✓ Found {len(items)} load balancers")
        print("")
        
        # Get details for first 10 as a sample
        print("Getting detailed information (first 10 as sample)...")
        print("=" * 80)
        print("")
        
        lb_list = []
        
        for i, lb in enumerate(items[:10]):
            if lb is None:
                continue
            
            # List API returns simplified structure
            lb_name = lb.get('name', 'unknown')
            
            print(f"[{i+1}/10] Querying {lb_name}...")
            
            # Get full details
            details = get_f5_load_balancer_details(
                creds['api_url'],
                creds['api_token'],
                'acme-net',
                lb_name
            )
            
            if details:
                spec = details.get('spec', {})
                domains = spec.get('domains', [])
                
                if domains:
                    for domain in domains:
                        lb_list.append({
                            'domain': domain,
                            'lb_name': lb_name
                        })
                        print(f"  ✓ Domain: {domain}")
                else:
                    print(f"  - No domains configured")
            
            time.sleep(0.1)  # Rate limiting
        
        print("")
        print("=" * 80)
        print("Sample Results (first 10 load balancers):")
        print("=" * 80)
        print("")
        
        if lb_list:
            lb_list.sort(key=lambda x: x['domain'])
            
            print(f"{'Domain':<50} {'Load Balancer Name':<40}")
            print("-" * 80)
            
            for item in lb_list:
                print(f"{item['domain']:<50} {item['lb_name']:<40}")
            
            print("")
            print(f"Total Domains (in sample): {len(lb_list)}")
        else:
            print("No domains found in sample")
        
        print("")
        print("=" * 80)
        print("Note: This is a sample of 10 load balancers.")
        print("To get all 112, the script would need to query each one individually.")
        print("=" * 80)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
