"""
Credential Manager for AWS Operations Agent.

This module provides credential management functionality including:
- STS AssumeRole for cross-account access
- Credential caching with expiration tracking
- Automatic credential refresh
- boto3 client factory with assumed credentials
"""

import os
import boto3
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class CredentialManager:
    """
    Manages AWS credentials for the agent, including role assumption,
    caching, and automatic refresh.
    """

    def __init__(self, cross_account_role_name: str = None):
        """
        Initialize the CredentialManager.

        Args:
            cross_account_role_name: Name of the cross-account role to assume in target accounts
        """
        self.cross_account_role_name = cross_account_role_name or os.environ.get(
            'CROSS_ACCOUNT_ROLE_NAME', 'aws-ops-agent-cross-account-role'
        )
        self.credentials_cache: Dict[str, Dict[str, Any]] = {}
        self._sts_client = boto3.client('sts')
        
        # Get current account ID for logging
        try:
            self.current_account_id = self._sts_client.get_caller_identity()['Account']
        except Exception:
            self.current_account_id = 'unknown'

    def get_boto3_client(
        self,
        service_name: str,
        account_id: Optional[str] = None,
        region_name: Optional[str] = None,
        request_id: str = 'unknown'
    ) -> boto3.client:
        """
        Get a boto3 client with assumed role credentials.

        Args:
            service_name: AWS service name (e.g., 'route53', 'elbv2')
            account_id: Target account ID for cross-account access (optional)
            region_name: AWS region name (default: None, uses default region)
            request_id: Request ID for logging (default: 'unknown')

        Returns:
            Configured boto3 client with assumed credentials or default credentials

        Raises:
            ClientError: If role assumption fails
        """
        # If no account_id specified or same as current account, use default credentials
        if not account_id or account_id == self.current_account_id:
            logger.debug(f"Using default credentials for {service_name}")
            if region_name:
                return boto3.client(service_name, region_name=region_name)
            return boto3.client(service_name)

        # For cross-account access, construct role ARN for target account
        role_arn = f"arn:aws:iam::{account_id}:role/{self.cross_account_role_name}"

        # Get or refresh credentials
        credentials = self._get_cached_credentials(role_arn, request_id)

        # Create and return boto3 client with assumed credentials
        client_kwargs = {
            'aws_access_key_id': credentials['AccessKeyId'],
            'aws_secret_access_key': credentials['SecretAccessKey'],
            'aws_session_token': credentials['SessionToken']
        }
        if region_name:
            client_kwargs['region_name'] = region_name

        return boto3.client(service_name, **client_kwargs)

    def assume_role(self, role_arn: str, session_name: Optional[str] = None, request_id: str = 'unknown') -> Dict[str, Any]:
        """
        Assume an IAM role and return temporary credentials.

        Args:
            role_arn: ARN of the role to assume
            session_name: Optional session name (default: 'aws-ops-agent-session')
            request_id: Request ID for logging (default: 'unknown')

        Returns:
            Dictionary containing:
                - AccessKeyId: str
                - SecretAccessKey: str
                - SessionToken: str
                - Expiration: datetime

        Raises:
            ClientError: If role assumption fails due to permissions or other errors
        """
        if session_name is None:
            session_name = 'aws-ops-agent-session'

        # Extract target account ID from role ARN for logging
        target_account_id = role_arn.split(':')[4] if ':' in role_arn else 'unknown'

        try:
            logger.info(f"Assuming role: {role_arn}")
            response = self._sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                ExternalId='aws-ops-agent',
                DurationSeconds=3600  # 1 hour
            )

            credentials = response['Credentials']
            logger.info(f"Successfully assumed role: {role_arn}")

            # Log successful cross-account access
            self._log_cross_account_access(
                operation='assume_role',
                source_account=self.current_account_id,
                target_account=target_account_id,
                role_arn=role_arn,
                success=True,
                request_id=request_id
            )

            return {
                'AccessKeyId': credentials['AccessKeyId'],
                'SecretAccessKey': credentials['SecretAccessKey'],
                'SessionToken': credentials['SessionToken'],
                'Expiration': credentials['Expiration']
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            logger.error(
                f"Failed to assume role {role_arn}: {error_code} - {error_message}"
            )

            # Log failed cross-account access
            self._log_cross_account_access(
                operation='assume_role',
                source_account=self.current_account_id,
                target_account=target_account_id,
                role_arn=role_arn,
                success=False,
                request_id=request_id,
                error_message=f"{error_code}: {error_message}"
            )

            # Provide helpful error messages
            if error_code == 'AccessDenied':
                raise ClientError(
                    {
                        'Error': {
                            'Code': 'AccessDenied',
                            'Message': (
                                f"Permission denied when assuming role {role_arn}. "
                                f"Ensure the Lambda execution role has sts:AssumeRole "
                                f"permission for this role."
                            )
                        }
                    },
                    'AssumeRole'
                )
            else:
                raise

    def _get_cached_credentials(self, role_arn: str, request_id: str = 'unknown') -> Dict[str, Any]:
        """
        Get credentials from cache or assume role if not cached or expired.

        Args:
            role_arn: ARN of the role to get credentials for
            request_id: Request ID for logging

        Returns:
            Dictionary containing credential information
        """
        # Check if credentials are cached and still valid
        if role_arn in self.credentials_cache:
            cached_creds = self.credentials_cache[role_arn]
            expiration = cached_creds['Expiration']

            # Check if credentials are still valid (with 5-minute buffer)
            now = datetime.now(timezone.utc)
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)

            time_until_expiration = (expiration - now).total_seconds()

            if time_until_expiration > 300:  # More than 5 minutes remaining
                logger.debug(f"Using cached credentials for {role_arn}")
                return cached_creds

            logger.info(f"Cached credentials for {role_arn} expired or expiring soon")

        # Credentials not cached or expired, assume role
        credentials = self.assume_role(role_arn, request_id=request_id)

        # Cache the credentials
        self.credentials_cache[role_arn] = credentials

        return credentials

    def _log_cross_account_access(
        self,
        operation: str,
        source_account: str,
        target_account: str,
        role_arn: str,
        success: bool,
        request_id: str,
        error_message: Optional[str] = None
    ) -> None:
        """Log cross-account access attempts."""
        try:
            # Import here to avoid circular imports
            from src.agent.cloudwatch_logger import cloudwatch_logger
            
            cloudwatch_logger.log_cross_account_access(
                operation=operation,
                source_account=source_account,
                target_account=target_account,
                role_arn=role_arn,
                success=success,
                request_id=request_id,
                error_message=error_message
            )
        except ImportError:
            # Fallback to basic logging if cloudwatch_logger is not available
            logger.info(
                f"Cross-account access: {operation} from {source_account} to {target_account} "
                f"using {role_arn} - Success: {success}"
            )

    def clear_cache(self) -> None:
        """
        Clear the credentials cache.

        This is useful for testing or forcing credential refresh.
        """
        logger.debug("Clearing credentials cache")
        self.credentials_cache.clear()

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache state.

        Returns:
            Dictionary containing cache statistics
        """
        cache_info = {
            'cached_roles': list(self.credentials_cache.keys()),
            'cache_size': len(self.credentials_cache)
        }

        # Add expiration info for each cached role
        for role_arn, creds in self.credentials_cache.items():
            expiration = creds['Expiration']
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            time_until_expiration = (expiration - now).total_seconds()

            cache_info[f'{role_arn}_expires_in_seconds'] = time_until_expiration

        return cache_info
