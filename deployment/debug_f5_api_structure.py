#!/usr/bin/env python3
"""
Debug F5 API structure to see what's actually returned
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

# Main
if __name__ == "__main__":
    print("=" * 80)
    print("F5 API Structure Debug")
    print("=" * 80)
    print("")
    
    try:
        # Get credentials
        creds = get_f5_credentials()
        
        headers = {
            'Authorization': f'APIToken {creds["api_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Query List API
        print("1. List API Response Structure:")
        print("-" * 80)
        url = f"{creds['api_url']}/config/namespaces/acme-net/http_loadbalancers"
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()
        
        items = data.get('items', [])
        print(f"Total items: {len(items)}")
        
        if items:
            print("\nFirst item structure:")
            print(json.dumps(items[0], indent=2))
            
            # Check if it has spec
            if 'spec' in items[0]:
                print("\n✓ List API DOES include 'spec'")
                if 'domains' in items[0].get('spec', {}):
                    print("✓ List API DOES include 'domains' in spec")
                else:
                    print("✗ List API does NOT include 'domains' in spec")
            else:
                print("\n✗ List API does NOT include 'spec'")
        
        print("\n" + "=" * 80)
        print("2. Get API Response Structure (for go1-pd-example-app):")
        print("-" * 80)
        
        url2 = f"{creds['api_url']}/config/namespaces/acme-net/http_loadbalancers/go1-pd-example-app"
        response2 = requests.get(url2, headers=headers, timeout=30)
        data2 = response2.json()
        
        print(json.dumps(data2, indent=2)[:2000])  # First 2000 chars
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
