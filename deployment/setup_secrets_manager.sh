#!/bin/bash
# Setup AWS Secrets Manager for F5 API credentials

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SECRET_NAME="${F5_SECRET_NAME:-f5-distributed-cloud-api-credentials}"
SECRET_DESCRIPTION="F5 Distributed Cloud API credentials for AWS Operations Agent"

# Print functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured or invalid"
        exit 1
    fi
    
    # Check jq for JSON processing
    if ! command -v jq &> /dev/null; then
        print_warning "jq is not installed - JSON output will not be formatted"
    fi
    
    print_info "All prerequisites satisfied"
}

# Display configuration
display_config() {
    print_step "Configuration"
    echo "  Secret Name: $SECRET_NAME"
    echo "  Description: $SECRET_DESCRIPTION"
    echo "  Region: $(aws configure get region)"
    echo "  Account: $(aws sts get-caller-identity --query Account --output text)"
    echo ""
}

# Create F5 credentials secret
create_f5_secret() {
    print_step "Creating F5 API credentials secret..."
    
    # Check if secret already exists
    if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" &> /dev/null; then
        print_warning "Secret $SECRET_NAME already exists"
        
        # Ask user if they want to update
        read -p "Do you want to update the existing secret? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Skipping secret creation"
            return 0
        fi
        
        UPDATE_SECRET=true
    else
        UPDATE_SECRET=false
    fi
    
    # Get F5 credentials from user
    print_info "Please provide your F5 Distributed Cloud API credentials:"
    echo ""
    
    # API URL
    read -p "F5 API URL (e.g., https://your-tenant.console.ves.volterra.io/api): " F5_API_URL
    if [ -z "$F5_API_URL" ]; then
        print_error "F5 API URL is required"
        exit 1
    fi
    
    # API Token
    read -s -p "F5 API Token: " F5_API_TOKEN
    echo
    if [ -z "$F5_API_TOKEN" ]; then
        print_error "F5 API Token is required"
        exit 1
    fi
    
    # Namespace (optional)
    read -p "F5 Namespace (optional, default: system): " F5_NAMESPACE
    F5_NAMESPACE="${F5_NAMESPACE:-system}"
    
    # Create JSON secret value
    SECRET_VALUE=$(cat << EOF
{
  "api_url": "$F5_API_URL",
  "api_token": "$F5_API_TOKEN",
  "namespace": "$F5_NAMESPACE"
}
EOF
)
    
    # Create or update secret
    if [ "$UPDATE_SECRET" = true ]; then
        print_info "Updating existing secret..."
        aws secretsmanager update-secret \
            --secret-id "$SECRET_NAME" \
            --description "$SECRET_DESCRIPTION" \
            --secret-string "$SECRET_VALUE"
    else
        print_info "Creating new secret..."
        aws secretsmanager create-secret \
            --name "$SECRET_NAME" \
            --description "$SECRET_DESCRIPTION" \
            --secret-string "$SECRET_VALUE" \
            --tags Key=Application,Value=aws-ops-agent Key=ManagedBy,Value=Script
    fi
    
    if [ $? -eq 0 ]; then
        print_info "F5 credentials secret created/updated successfully"
    else
        print_error "Failed to create/update F5 credentials secret"
        exit 1
    fi
}

# Set up secret rotation (optional)
setup_rotation() {
    print_step "Setting up secret rotation (optional)..."
    
    read -p "Do you want to enable automatic secret rotation? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping secret rotation setup"
        return 0
    fi
    
    print_warning "Automatic rotation requires a Lambda function to handle the rotation"
    print_info "This is an advanced feature - see AWS documentation for details"
    print_info "For now, manual rotation is recommended"
    
    # TODO: Implement rotation Lambda function
    # aws secretsmanager rotate-secret \
    #     --secret-id "$SECRET_NAME" \
    #     --rotation-lambda-arn "arn:aws:lambda:region:account:function:f5-secret-rotation" \
    #     --rotation-rules AutomaticallyAfterDays=30
}

# Grant Lambda access to secret
grant_lambda_access() {
    print_step "Granting Lambda execution role access to secret..."
    
    # Get Lambda execution role ARN
    LAMBDA_ROLE_NAME="aws-ops-agent-execution-role"
    
    if ! aws iam get-role --role-name "$LAMBDA_ROLE_NAME" &> /dev/null; then
        print_warning "Lambda execution role $LAMBDA_ROLE_NAME not found"
        print_info "Make sure to deploy IAM roles first (see deployment/iam-deployment-guide.md)"
        return 0
    fi
    
    LAMBDA_ROLE_ARN=$(aws iam get-role --role-name "$LAMBDA_ROLE_NAME" --query 'Role.Arn' --output text)
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region)
    
    # Create resource policy for the secret
    RESOURCE_POLICY=$(cat << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "$LAMBDA_ROLE_ARN"
      },
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "*"
    }
  ]
}
EOF
)
    
    # Apply resource policy
    aws secretsmanager put-resource-policy \
        --secret-id "$SECRET_NAME" \
        --resource-policy "$RESOURCE_POLICY"
    
    if [ $? -eq 0 ]; then
        print_info "Lambda access granted successfully"
    else
        print_warning "Failed to grant Lambda access - check IAM permissions"
    fi
}

# Test secret access
test_secret_access() {
    print_step "Testing secret access..."
    
    # Test retrieving the secret
    print_info "Retrieving secret value..."
    SECRET_OUTPUT=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --query 'SecretString' --output text)
    
    if [ $? -eq 0 ]; then
        print_info "Secret retrieved successfully"
        
        # Parse and display (without sensitive data)
        if command -v jq &> /dev/null; then
            API_URL=$(echo "$SECRET_OUTPUT" | jq -r '.api_url')
            NAMESPACE=$(echo "$SECRET_OUTPUT" | jq -r '.namespace')
            
            echo "  API URL: $API_URL"
            echo "  Namespace: $NAMESPACE"
            echo "  API Token: [HIDDEN]"
        else
            echo "  Secret contains F5 API credentials (use jq to parse JSON)"
        fi
    else
        print_error "Failed to retrieve secret"
        exit 1
    fi
}

# Display results
display_results() {
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region)
    SECRET_ARN="arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${SECRET_NAME}"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Secrets Manager Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Created Resources:"
    echo "  🔐 Secret Name: $SECRET_NAME"
    echo "  🔐 Secret ARN: $SECRET_ARN"
    echo "  🔐 Region: $REGION"
    echo ""
    echo "Environment Variable for Lambda:"
    echo "  F5_SECRET_NAME=$SECRET_NAME"
    echo ""
    echo "Next Steps:"
    echo "  1. Deploy Lambda function with F5_SECRET_NAME environment variable"
    echo "  2. Test F5 API connectivity from Lambda"
    echo "  3. (Optional) Set up secret rotation"
    echo "  4. Monitor secret access in CloudTrail"
    echo ""
    echo "Security Notes:"
    echo "  - Secret is encrypted at rest using AWS KMS"
    echo "  - Access is logged in CloudTrail"
    echo "  - Only Lambda execution role can access the secret"
    echo "  - Consider enabling secret rotation for production"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Set up AWS Secrets Manager for F5 API credentials"
    echo ""
    echo "Options:"
    echo "  -n, --secret-name NAME  Secret name (default: f5-distributed-cloud-api-credentials)"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  F5_SECRET_NAME         Name of the secret to create (default: f5-distributed-cloud-api-credentials)"
    echo ""
    echo "Examples:"
    echo "  # Create secret with default name"
    echo "  $0"
    echo ""
    echo "  # Create secret with custom name"
    echo "  $0 --secret-name my-f5-credentials"
    echo ""
    echo "Required Information:"
    echo "  - F5 Distributed Cloud API URL"
    echo "  - F5 API Token"
    echo "  - F5 Namespace (optional)"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--secret-name)
            SECRET_NAME="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo ""
    print_info "AWS Operations Agent - Secrets Manager Setup"
    echo ""
    
    check_prerequisites
    display_config
    create_f5_secret
    setup_rotation
    grant_lambda_access
    test_secret_access
    display_results
}

# Run main function
main "$@"