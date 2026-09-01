"""
Property-based tests for credential caching.

Feature: aws-ops-agent, Property 15: Credential caching
Validates: Requirements 4.6, 8.5

Property 15: Credential caching
For any assumed role credentials, the agent should cache them for the duration
of their validity and reuse them for subsequent API calls within the same session.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings

from src.credentials import CredentialManager


# Strategies for generating test data
@st.composite
def role_arn_strategy(draw):
    """Generate valid AWS IAM role ARNs."""
    account_id = draw(st.integers(min_value=100000000000, max_value=999999999999))
    role_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
        min_size=1,
        max_size=64
    ).filter(lambda x: x and x[0].isalnum()))
    
    return f"arn:aws:iam::{account_id}:role/{role_name}"


@st.composite
def service_name_strategy(draw):
    """Generate valid AWS service names."""
    return draw(st.sampled_from([
        'route53', 'cloudfront', 'elbv2', 'ec2', 'athena',
        's3', 'sts', 'secretsmanager', 'logs', 'iam'
    ]))


@st.composite
def credentials_strategy(draw):
    """Generate mock AWS credentials."""
    access_key = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Nd')),
        min_size=20,
        max_size=20
    ))
    secret_key = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='+/'),
        min_size=40,
        max_size=40
    ))
    session_token = draw(st.text(min_size=100, max_size=200))
    
    # Generate expiration time in the future (between 30 minutes and 2 hours)
    minutes_until_expiry = draw(st.integers(min_value=30, max_value=120))
    expiration = datetime.now(timezone.utc) + timedelta(minutes=minutes_until_expiry)
    
    return {
        'AccessKeyId': access_key,
        'SecretAccessKey': secret_key,
        'SessionToken': session_token,
        'Expiration': expiration
    }


class TestCredentialCachingProperty:
    """Property-based tests for credential caching."""

    @given(
        role_arn=role_arn_strategy(),
        credentials=credentials_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_credentials_cached_and_reused(self, role_arn, credentials):
        """
        Feature: aws-ops-agent, Property 15: Credential caching
        
        For any assumed role credentials, the agent should cache them for the
        duration of their validity and reuse them for subsequent API calls
        within the same session.
        
        This test verifies that:
        1. Credentials are cached after first assumption
        2. Subsequent calls reuse cached credentials
        3. No additional AssumeRole calls are made while credentials are valid
        """
        with patch('boto3.client') as mock_boto3_client:
            # Create mock STS client
            mock_sts_client = Mock()
            mock_boto3_client.return_value = mock_sts_client
            
            # Configure mock to return credentials
            mock_sts_client.assume_role.return_value = {
                'Credentials': {
                    'AccessKeyId': credentials['AccessKeyId'],
                    'SecretAccessKey': credentials['SecretAccessKey'],
                    'SessionToken': credentials['SessionToken'],
                    'Expiration': credentials['Expiration']
                }
            }
            
            # Create credential manager
            manager = CredentialManager(sso_role_arn=role_arn)
            manager._sts_client = mock_sts_client
            
            # First call - should assume role
            creds1 = manager._get_cached_credentials(role_arn)
            initial_assume_count = mock_sts_client.assume_role.call_count
            
            # Verify credentials were returned
            assert creds1['AccessKeyId'] == credentials['AccessKeyId']
            assert creds1['SecretAccessKey'] == credentials['SecretAccessKey']
            assert creds1['SessionToken'] == credentials['SessionToken']
            assert initial_assume_count == 1
            
            # Second call - should use cached credentials
            creds2 = manager._get_cached_credentials(role_arn)
            second_assume_count = mock_sts_client.assume_role.call_count
            
            # Property: No additional AssumeRole call should be made
            assert second_assume_count == initial_assume_count, \
                "Credentials should be cached and reused without additional AssumeRole calls"
            
            # Property: Cached credentials should be identical to original
            assert creds2['AccessKeyId'] == creds1['AccessKeyId']
            assert creds2['SecretAccessKey'] == creds1['SecretAccessKey']
            assert creds2['SessionToken'] == creds1['SessionToken']
            assert creds2['Expiration'] == creds1['Expiration']

    @given(
        role_arn=role_arn_strategy(),
        service_name=service_name_strategy(),
        credentials=credentials_strategy(),
        num_calls=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_multiple_client_requests_use_cache(
        self, role_arn, service_name, credentials, num_calls
    ):
        """
        Feature: aws-ops-agent, Property 15: Credential caching
        
        For any number of boto3 client requests within a session, credentials
        should be cached and reused, resulting in only one AssumeRole call.
        
        This test verifies that multiple get_boto3_client calls reuse cached
        credentials without making additional AssumeRole API calls.
        """
        with patch('boto3.client') as mock_boto3_client:
            # Create mock STS client
            mock_sts_client = Mock()
            
            # Create mock service client
            mock_service_client = Mock()
            
            def client_factory(service, **kwargs):
                if service == 'sts':
                    return mock_sts_client
                return mock_service_client
            
            mock_boto3_client.side_effect = client_factory
            
            # Configure mock to return credentials
            mock_sts_client.assume_role.return_value = {
                'Credentials': {
                    'AccessKeyId': credentials['AccessKeyId'],
                    'SecretAccessKey': credentials['SecretAccessKey'],
                    'SessionToken': credentials['SessionToken'],
                    'Expiration': credentials['Expiration']
                }
            }
            
            # Create credential manager
            manager = CredentialManager(sso_role_arn=role_arn)
            manager._sts_client = mock_sts_client
            
            # Make multiple client requests
            clients = []
            for _ in range(num_calls):
                client = manager.get_boto3_client(service_name)
                clients.append(client)
            
            # Property: Only one AssumeRole call should be made regardless of num_calls
            assume_role_count = mock_sts_client.assume_role.call_count
            assert assume_role_count == 1, \
                f"Expected 1 AssumeRole call for {num_calls} client requests, got {assume_role_count}"
            
            # Property: All clients should be created successfully
            assert len(clients) == num_calls

    @given(
        role_arn=role_arn_strategy(),
        credentials=credentials_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_cache_persists_across_different_services(
        self, role_arn, credentials
    ):
        """
        Feature: aws-ops-agent, Property 15: Credential caching
        
        For any assumed role, credentials should be cached and reused across
        different AWS service client requests (route53, cloudfront, elbv2, etc.).
        
        This test verifies that the cache is keyed by role ARN, not by service name.
        """
        with patch('boto3.client') as mock_boto3_client:
            # Create mock STS client
            mock_sts_client = Mock()
            
            # Create mock service clients
            mock_service_clients = {}
            
            def client_factory(service, **kwargs):
                if service == 'sts':
                    return mock_sts_client
                if service not in mock_service_clients:
                    mock_service_clients[service] = Mock()
                return mock_service_clients[service]
            
            mock_boto3_client.side_effect = client_factory
            
            # Configure mock to return credentials
            mock_sts_client.assume_role.return_value = {
                'Credentials': {
                    'AccessKeyId': credentials['AccessKeyId'],
                    'SecretAccessKey': credentials['SecretAccessKey'],
                    'SessionToken': credentials['SessionToken'],
                    'Expiration': credentials['Expiration']
                }
            }
            
            # Create credential manager
            manager = CredentialManager(sso_role_arn=role_arn)
            manager._sts_client = mock_sts_client
            
            # Request clients for different services
            services = ['route53', 'cloudfront', 'elbv2', 'athena']
            for service in services:
                manager.get_boto3_client(service)
            
            # Property: Only one AssumeRole call should be made for all services
            assume_role_count = mock_sts_client.assume_role.call_count
            assert assume_role_count == 1, \
                f"Expected 1 AssumeRole call for {len(services)} different services, got {assume_role_count}"

    @given(
        role_arn=role_arn_strategy(),
        credentials=credentials_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_cache_cleared_on_clear_cache(self, role_arn, credentials):
        """
        Feature: aws-ops-agent, Property 15: Credential caching
        
        For any cached credentials, calling clear_cache() should remove them
        from the cache, forcing a new AssumeRole call on the next request.
        
        This test verifies that the cache can be explicitly cleared.
        """
        with patch('boto3.client') as mock_boto3_client:
            # Create mock STS client
            mock_sts_client = Mock()
            mock_boto3_client.return_value = mock_sts_client
            
            # Configure mock to return credentials
            mock_sts_client.assume_role.return_value = {
                'Credentials': {
                    'AccessKeyId': credentials['AccessKeyId'],
                    'SecretAccessKey': credentials['SecretAccessKey'],
                    'SessionToken': credentials['SessionToken'],
                    'Expiration': credentials['Expiration']
                }
            }
            
            # Create credential manager
            manager = CredentialManager(sso_role_arn=role_arn)
            manager._sts_client = mock_sts_client
            
            # First call - should assume role
            manager._get_cached_credentials(role_arn)
            assert mock_sts_client.assume_role.call_count == 1
            
            # Second call - should use cache
            manager._get_cached_credentials(role_arn)
            assert mock_sts_client.assume_role.call_count == 1
            
            # Clear cache
            manager.clear_cache()
            
            # Property: Cache should be empty after clear
            assert len(manager.credentials_cache) == 0
            
            # Third call - should assume role again
            manager._get_cached_credentials(role_arn)
            
            # Property: AssumeRole should be called again after cache clear
            assert mock_sts_client.assume_role.call_count == 2

    @given(
        role_arns=st.lists(role_arn_strategy(), min_size=2, max_size=5, unique=True)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_15_separate_cache_per_role(self, role_arns):
        """
        Feature: aws-ops-agent, Property 15: Credential caching
        
        For any set of different role ARNs, each should have its own cache entry,
        and credentials should not be shared between different roles.
        
        This test verifies that the cache correctly isolates credentials by role ARN.
        """
        with patch('boto3.client') as mock_boto3_client:
            # Create mock STS client
            mock_sts_client = Mock()
            mock_boto3_client.return_value = mock_sts_client
            
            # Configure mock to return different credentials for each role
            # Use the role ARN itself to generate unique credentials
            def assume_role_side_effect(**kwargs):
                role_arn = kwargs['RoleArn']
                # Generate unique credentials based on role ARN
                unique_id = str(hash(role_arn))[-10:]
                return {
                    'Credentials': {
                        'AccessKeyId': f'AKIA{unique_id}EXAMPLE',
                        'SecretAccessKey': f'SECRET{unique_id}KEY',
                        'SessionToken': f'TOKEN{unique_id}SESSION',
                        'Expiration': datetime.now(timezone.utc) + timedelta(hours=1)
                    }
                }
            
            mock_sts_client.assume_role.side_effect = assume_role_side_effect
            
            # Create credential manager with first role
            manager = CredentialManager(sso_role_arn=role_arns[0])
            manager._sts_client = mock_sts_client
            
            # Get credentials for each role
            cached_creds = {}
            for role_arn in role_arns:
                creds = manager._get_cached_credentials(role_arn)
                cached_creds[role_arn] = creds
            
            # Property: Should have made one AssumeRole call per unique role
            assert mock_sts_client.assume_role.call_count == len(role_arns)
            
            # Property: Each role should have different credentials in cache
            access_keys = [creds['AccessKeyId'] for creds in cached_creds.values()]
            assert len(set(access_keys)) == len(role_arns), \
                "Each role should have unique credentials"
            
            # Property: Cache should contain all roles
            assert len(manager.credentials_cache) == len(role_arns)
            
            # Get credentials again for each role
            for role_arn in role_arns:
                manager._get_cached_credentials(role_arn)
            
            for role_arn in role_arns:
                manager._get_cached_credentials(role_arn)
            
            # Property: Should not make additional AssumeRole calls (using cache)
            assert mock_sts_client.assume_role.call_count == len(role_arns)
