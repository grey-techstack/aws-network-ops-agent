#!/usr/bin/env bash

# If someone runs: sh aws-assume-role.sh ...
# /bin/sh may be dash (no pipefail / no [[ / no printf %q). Re-run under bash.
if [ -z "${BASH_VERSION:-}" ]; then
  if command -v bash >/dev/null 2>&1; then
    exec bash "$0" "$@"
  fi
  echo "Error: bash is required (try: bash $0 ...)" >&2
  exit 127
fi

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  eval "$(aws-assume-role.sh <role-arn> [session-name] [duration-seconds])"

Examples:
  eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/SupportAccessRole MySession 3600)"
  aws sts get-caller-identity

Notes:
  - This script PRINTS export statements; use eval/source so exports apply to your current shell.
  - Requires AWS CLI v2 (or v1) to be installed.
EOF
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

ROLE_ARN=${1:-}
if [[ -z "$ROLE_ARN" ]]; then
  usage >&2
  exit 2
fi

SESSION_NAME=${2:-"${USER:-session}-$(date -u +%Y%m%dT%H%M%SZ)"}
DURATION_SECONDS=${3:-3600}

# Optional: respect AWS_REGION/AWS_DEFAULT_REGION if set, otherwise let AWS CLI decide.
# shellcheck disable=SC2153

assume_out=$(
  aws sts assume-role \
    --role-arn "$ROLE_ARN" \
    --role-session-name "$SESSION_NAME" \
    --duration-seconds "$DURATION_SECONDS" \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken,Expiration]' \
    --output text
)

# Output format: <AccessKeyId> <SecretAccessKey> <SessionToken> <Expiration>
# SessionToken never contains spaces.
read -r access_key_id secret_access_key session_token expiration <<<"$assume_out"

# Print shell-escaped exports so caller can eval/source it safely.
printf 'export AWS_ACCESS_KEY_ID=%q\n' "$access_key_id"
printf 'export AWS_SECRET_ACCESS_KEY=%q\n' "$secret_access_key"
printf 'export AWS_SESSION_TOKEN=%q\n' "$session_token"
printf 'export AWS_CREDENTIAL_EXPIRATION=%q\n' "$expiration"

# Optional quality-of-life: mark that these came from assume-role.
printf 'export AWS_ASSUMED_ROLE_ARN=%q\n' "$ROLE_ARN"
printf 'export AWS_ASSUMED_ROLE_SESSION_NAME=%q\n' "$SESSION_NAME"
