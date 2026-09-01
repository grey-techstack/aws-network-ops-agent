#!/usr/bin/env python3
"""
List all F5 load balancers in acme-net namespace with their domains
"""

import os
import sys
import json
import boto3
import requests

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

# Query F5 API for load balancers
def query_f5_load_balancers(api_url, api_token, namespace):
    headers = {
        'Authorization': f'APIToken {api_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = f"{api_url}/config/namespaces/{namespace}/http_loadbalancers"
    
    print(f"Querying F5 API: {url}")
    print(f"Namespace: {namespace}")
    print("")
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    return data

# Main
if __name__ == "__main__":
    print("=" * 80)
    print("F5 Load Balancers in acme-net namespace")
    print("=" * 80)
    print("")
    
    try:
        # Get credentials
        print("Getting F5 credentials...")
        creds = get_f5_credentials()
        print("✓ Credentials retrieved")
        print("")
        
        # Query F5 API
        print("Querying F5 API...")
        data = query_f5_load_balancers(
            creds['api_url'],
            creds['api_token'],
            'acme-net'
        )
        print("✓ API query successful")
        print("")
        
        # List all load balancers
        items = data.get('items', [])
        
        print(f"Total Load Balancers: {len(items)}")
        print("=" * 80)
        print("")
        
        # Collect and sort by domain
        lb_list = []
        
        for lb in items:
            if lb is None:
                continue
                
            metadata = lb.get('metadata', {})
            spec = lb.get('spec', {})
            
            if metadata is None or spec is None:
                continue
            
            lb_name = metadata.get('name', 'unknown')
            domains = spec.get('domains', [])
            
            if domains is None:
                domains = []
            
            for domain in domains:
                lb_list.append({
                    'domain': domain,
                    'lb_name': lb_name
                })
        
        # Sort by domain
        lb_list.sort(key=lambda x: x['domain'])
        
        # Print in columns
        print(f"{'Domain':<50} {'Load Balancer Name':<40}")
        print("-" * 80)
        
        for item in lb_list:
            print(f"{item['domain']:<50} {item['lb_name']:<40}")
        
        print("")
        print("=" * 80)
        print(f"Total Domains: {len(lb_list)}")
        print("=" * 80)
        
        # Save to file
        output_file = "f5_load_balancers.json"
        with open(output_file, 'w') as f:
            json.dump(lb_list, f, indent=2)
        
        print(f"\n✓ Full list saved to: {output_file}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
