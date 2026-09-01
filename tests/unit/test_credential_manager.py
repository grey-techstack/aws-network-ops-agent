"""
Unit tests for CredentialManager.

Tests credential management functionality including role assumption,
caching, and automatic refresh.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from src.credentials import CredentialManager


class TestCredentialManager:
    """Test suite for CredentialManager class."""

    @pytest.fixture
    def mock_sts_client(self):
        """Create a mock STS client."""
        with patch('boto3.client') as mock_client:
            mock_sts = Mock()
            mock_client.return_value = mock_sts
            yield mock_sts

    @pytest.fixture
    def credential_manager(self, mock_sts_client):
        """Create a CredentialManager instance with mocked STS client."""
        manager = CredentialManager(sso_role_arn='arn:aws:iam::123456789012:role/GlobalReader')
        manager._sts_client = mock_sts_client
        return manager

    @pytest.fixture
    def mock_credentials(self):
        """Create mock credentials response."""
        return {
            'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
            'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'SessionToken': 'FwoGZXIvYXdzEBYaDH...',
            'Expiration': datetime.now(timezone.utc) + timedelta(hours=1)
        }

    def test_init(self):
        """Test CredentialManager initialization."""
        role_arn = 'arn:aws:iam::123456789012:role/GlobalReader'
        manager = CredentialManager(sso_role_arn=role_arn)

        assert manager.sso_role_arn == role_arn
        assert manager.credentials_cache == {}
        assert manager._sts_client is not None

    def test_assume_role_success(self, credential_manager, mock_sts_client, mock_credentials):
        """Test successful role assumption."""
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': mock_credentials['AccessKeyId'],
                'SecretAccessKey': mock_credentials['SecretAccessKey'],
                'SessionToken': mock_credentials['SessionToken'],
                'Expiration': mock_credentials['Expiration']
            }
        }

        role_arn = 'arn:aws:iam::123456789012:role/TestRole'
        result = credential_manager.assume_role(role_arn)

        assert result['AccessKeyId'] == mock_credentials['AccessKeyId']
        assert result['SecretAccessKey'] == mock_credentials['SecretAccessKey']
        assert result['SessionToken'] == mock_credentials['SessionToken']
        assert result['Expiration'] == mock_credentials['Expiration']

        mock_sts_client.assume_role.assert_called_once_with(
            RoleArn=role_arn,
            RoleSessionName='aws-ops-agent-session',
            DurationSeconds=3600
        )

    def test_assume_role_with_custom_session_name(self, credential_manager, mock_sts_client, mock_credentials):
        """Test role assumption with custom session name."""
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': mock_credentials['AccessKeyId'],
                'SecretAccessKey': mock_credentials['SecretAccessKey'],
                'SessionToken': mock_credentials['SessionToken'],
                'Expiration': mock_credentials['Expiration']
            }
        }

        role_arn = 'arn:aws:iam::123456789012:role/TestRole'
        session_name = 'custom-session'
        credential_manager.assume_role(role_arn, session_name=session_name)

        mock_sts_client.assume_role.assert_called_once_with(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=3600
        )

    def test_assume_role_access_denied(self, credential_manager, mock_sts_client):
        """Test role assumption failure due to access denied."""
        mock_sts_client.assume_role.side_effect = ClientError(
            {
                'Error': {
                    'Code': 'AccessDenied',
                    'Message': 'User is not authorized to perform: sts:AssumeRole'
                }
            },
            'AssumeRole'
        )

        role_arn = 'arn:aws:iam::123456789012:role/TestRole'

        with pytest.raises(ClientError) as exc_info:
            credential_manager.assume_role(role_arn)

        assert 'AccessDenied' in str(exc_info.value)
        assert 'sts:AssumeRole' in str(exc_info.value)

    def test_credential_caching(self, credential_manager, mock_sts_client, mock_credentials):
        """Test that credentials are cached and reused."""
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': mock_credentials['AccessKeyId'],
                'SecretAccessKey': mock_credentials['SecretAccessKey'],
                'SessionToken': mock_credentials['SessionToken'],
                'Expiration': mock_credentials['Expiration']
            }
        }

        role_arn = 'arn:aws:iam::123456789012:role/TestRole'

        # First call should assume role
        creds1 = credential_manager._get_cached_credentials(role_arn)
        assert mock_sts_client.assume_role.call_count == 1

        # Second call should use cached credentials
        creds2 = credential_manager._get_cached_credentials(role_arn)
        assert mock_sts_client.assume_role.call_count == 1  # No additional call

        # Credentials should be the same
        assert creds1['AccessKeyId'] == creds2['AccessKeyId']
        assert creds1['SessionToken'] == creds2['SessionToken']

    def test_credential_refresh_on_expiration(self, credential_manager, mock_sts_client):
        """Test automatic credential refresh when expired."""
        # First set of credentials (expired)
        expired_creds = {
            'AccessKeyId': 'EXPIRED_KEY',
            'SecretAccessKey': 'EXPIRED_SECRET',
            'SessionToken': 'EXPIRED_TOKEN',
            'Expiration': datetime.now(timezone.utc) - timedelta(minutes=10)
        }

        # New credentials
        new_creds = {
            'AccessKeyId': 'NEW_KEY',
            'SecretAccessKey': 'NEW_SECRET',
            'SessionToken': 'NEW_TOKEN',
            'Expiration': datetime.now(timezone.utc) + timedelta(hours=1)
        }

        role_arn = 'arn:aws:iam::123456789012:role/TestRole'

        # Manually cache expired credentials
        credential_manager.credentials_cache[role_arn] = expired_creds

        # Mock assume_role to return new credentials
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': new_creds['AccessKeyId'],
                'SecretAccessKey': new_creds['SecretAccessKey'],
                'SessionToken': new_creds['SessionToken'],
                'Expiration': new_creds['Expiration']
            }
        }

        # Get credentials should refresh
        result = credential_manager._get_cached_credentials(role_arn)

        assert result['AccessKeyId'] == new_creds['AccessKeyId']
        assert mock_sts_client.assume_role.call_count == 1

    def test_credential_refresh_near_expiration(self, credential_manager, mock_sts_client):
        """Test credential refresh when near expiration (within 5 minutes)."""
        # Credentials expiring in 3 minutes
        near_expired_creds = {
            'AccessKeyId': 'NEAR_EXPIRED_KEY',
            'SecretAccessKey': 'NEAR_EXPIRED_SECRET',
            'SessionToken': 'NEAR_EXPIRED_TOKEN',
            'Expiration': datetime.now(timezone.utc) + timedelta(minutes=3)
        }

        # New credentials
        new_creds = {
            'AccessKeyId': 'NEW_KEY',
            'SecretAccessKey': 'NEW_SECRET',
            'SessionToken': 'NEW_TOKEN',
            'Expiration': datetime.now(timezone.utc) + timedelta(hours=1)
        }

        role_arn = 'arn:aws:iam::123456789012:role/TestRole'

        # Manually cache near-expired credentials
        credential_manager.credentials_cache[role_arn] = near_expired_creds

        # Mock assume_role to return new credentials
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': new_creds['AccessKeyId'],
                'SecretAccessKey': new_creds['SecretAccessKey'],
                'SessionToken': new_creds['SessionToken'],
                'Expiration': new_creds['Expiration']
            }
        }

        # Get credentials should refresh
        result = credential_manager._get_cached_credentials(role_arn)

        assert result['AccessKeyId'] == new_creds['AccessKeyId']
        assert mock_sts_client.assume_role.call_count == 1

    @patch('boto3.client')
    def test_get_boto3_client_with_sso_role(self, mock_boto3_client, credential_manager, mock_sts_client, mock_credentials):
        """Test getting boto3 client with SSO role credentials."""
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': mock_credentials['AccessKeyId'],
                'SecretAccessKey': mock_credentials['SecretAccessKey'],
                'SessionToken': mock_credentials['SessionToken'],
                'Expiration': mock_credentials['Expiration']
            }
        }

        # Create mock service client
        mock_service_client = Mock()
        mock_boto3_client.return_value = mock_service_client

        client = credential_manager.get_boto3_client('route53')

        # Should have called boto3.client with credentials
        mock_boto3_client.assert_called_with(
            'route53',
            region_name='us-east-1',
            aws_access_key_id=mock_credentials['AccessKeyId'],
            aws_secret_access_key=mock_credentials['SecretAccessKey'],
            aws_session_token=mock_credentials['SessionToken']
        )

        assert client == mock_service_client

    @patch('boto3.client')
    def test_get_boto3_client_cross_account(self, mock_boto3_client, credential_manager, mock_sts_client, mock_credentials):
        """Test getting boto3 client for cross-account access."""
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': mock_credentials['AccessKeyId'],
                'SecretAccessKey': mock_credentials['SecretAccessKey'],
                'SessionToken': mock_credentials['SessionToken'],
                'Expiration': mock_credentials['Expiration']
            }
        }

        # Create mock service client
        mock_service_client = Mock()
        mock_boto3_client.return_value = mock_service_client

        target_account_id = '987654321098'
        client = credential_manager.get_boto3_client('elbv2', account_id=target_account_id)

        # Should have assumed role in target account
        expected_role_arn = f'arn:aws:iam::{target_account_id}:role/GlobalReader'
        mock_sts_client.assume_role.assert_called_once()
        call_args = mock_sts_client.assume_role.call_args
        assert call_args[1]['RoleArn'] == expected_role_arn

        assert client == mock_service_client

    def test_clear_cache(self, credential_manager, mock_credentials):
        """Test clearing the credentials cache."""
        # Add some credentials to cache
        credential_manager.credentials_cache['role1'] = mock_credentials
        credential_manager.credentials_cache['role2'] = mock_credentials

        assert len(credential_manager.credentials_cache) == 2

        # Clear cache
        credential_manager.clear_cache()

        assert len(credential_manager.credentials_cache) == 0

    def test_get_cache_info(self, credential_manager, mock_credentials):
        """Test getting cache information."""
        role_arn = 'arn:aws:iam::123456789012:role/TestRole'
        credential_manager.credentials_cache[role_arn] = mock_credentials

        cache_info = credential_manager.get_cache_info()

        assert cache_info['cache_size'] == 1
        assert role_arn in cache_info['cached_roles']
        assert f'{role_arn}_expires_in_seconds' in cache_info
        assert cache_info[f'{role_arn}_expires_in_seconds'] > 0

    def test_get_cache_info_empty(self, credential_manager):
        """Test getting cache info when cache is empty."""
        cache_info = credential_manager.get_cache_info()

        assert cache_info['cache_size'] == 0
        assert cache_info['cached_roles'] == []
