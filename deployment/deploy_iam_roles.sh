#!/bin/bash
# Deploy IAM roles and policies for AWS Operations Agent

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="${STACK_NAME:-aws-ops-agent-iam}"
GLOBAL_READER_ROLE_NAME="${GLOBAL_READER_ROLE_NAME:-GlobalReaderRole}"
F5_SECRET_NAME="${F5_SECRET_NAME:-f5-distributed-cloud-api-credentials}"
CORE_NETWORK_ACCOUNT_ID="${CORE_NETWORK_ACCOUNT_ID}"
WORKLOAD_ACCOUNT_IDS="${WORKLOAD_ACCOUNT_IDS}"

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
    
    # Check required environment variables
    if [ -z "$CORE_NETWORK_ACCOUNT_ID" ]; then
        print_error "CORE_NETWORK_ACCOUNT_ID environment variable is required"
        print_info "Example: export CORE_NETWORK_ACCOUNT_ID=111111111111"
        exit 1
    fi
    
    if [ -z "$WORKLOAD_ACCOUNT_IDS" ]; then
        print_error "WORKLOAD_ACCOUNT_IDS environment variable is required"
        print_info "Example: export WORKLOAD_ACCOUNT_IDS=222222222222,333333333333"
        exit 1
    fi
    
    # Validate account ID format
    if ! [[ "$CORE_NETWORK_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
        print_error "CORE_NETWORK_ACCOUNT_ID must be a 12-digit AWS Account ID"
        exit 1
    fi
    
    print_info "All prerequisites satisfied"
}

# Display configuration
display_config() {
    print_step "Deployment Configuration"
    echo "  Stack Name: $STACK_NAME"
    echo "  Global Reader Role: $GLOBAL_READER_ROLE_NAME"
    echo "  F5 Secret Name: $F5_SECRET_NAME"
    echo "  Core Network Account: $CORE_NETWORK_ACCOUNT_ID"
    echo "  Workload Accounts: $WORKLOAD_ACCOUNT_IDS"
    echo ""
}

# Deploy using CloudFormation
deploy_cloudformation() {
    print_step "Deploying IAM roles using CloudFormation..."
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" &> /dev/null; then
        print_info "Stack $STACK_NAME exists, updating..."
        OPERATION="update-stack"
    else
        print_info "Creating new stack $STACK_NAME..."
        OPERATION="create-stack"
    fi
    
    # Deploy stack
    aws cloudformation $OPERATION \
        --stack-name "$STACK_NAME" \
        --template-body file://iam-roles.yaml \
        --parameters \
            ParameterKey=GlobalReaderRoleName,ParameterValue="$GLOBAL_READER_ROLE_NAME" \
            ParameterKey=F5SecretName,ParameterValue="$F5_SECRET_NAME" \
            ParameterKey=CoreNetworkAccountId,ParameterValue="$CORE_NETWORK_ACCOUNT_ID" \
            ParameterKey=WorkloadAccountIds,ParameterValue="$WORKLOAD_ACCOUNT_IDS" \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags \
            Key=Application,Value=aws-ops-agent \
            Key=ManagedBy,Value=CloudFormation
    
    print_info "CloudFormation deployment initiated"
    
    # Wait for stack completion
    print_info "Waiting for stack deployment to complete..."
    aws cloudformation wait stack-${OPERATION%-stack}-complete --stack-name "$STACK_NAME"
    
    if [ $? -eq 0 ]; then
        print_info "Stack deployment completed successfully"
    else
        print_error "Stack deployment failed"
        exit 1
    fi
}

# Deploy using AWS CLI
deploy_cli() {
    print_step "Deploying IAM roles using AWS CLI..."
    
    # Create Lambda execution role
    print_info "Creating Lambda execution role..."
    
    if aws iam get-role --role-name aws-ops-agent-execution-role &> /dev/null; then
        print_warning "Role aws-ops-agent-execution-role already exists, skipping creation"
    else
        aws iam create-role \
            --role-name aws-ops-agent-execution-role \
            --assume-role-policy-document file://iam-trust-policy.json \
            --description "Execution role for AWS Operations Agent Lambda function" \
            --tags Key=Application,Value=aws-ops-agent Key=ManagedBy,Value=CLI
        
        print_info "Lambda execution role created"
    fi
    
    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name aws-ops-agent-execution-role \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Create custom policy
    print_info "Creating custom IAM policy..."
    
    # Update permissions policy with actual account IDs
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region)
    
    # Create temporary policy file with substituted values
    cat > temp-permissions-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/aws-ops-agent:*"
    },
    {
      "Sid": "AssumeSSORoles",
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": [
        "arn:aws:iam::${ACCOUNT_ID}:role/${GLOBAL_READER_ROLE_NAME}",
        "arn:aws:iam::${CORE_NETWORK_ACCOUNT_ID}:role/${GLOBAL_READER_ROLE_NAME}",
        "arn:aws:iam::*:role/${GLOBAL_READER_ROLE_NAME}"
      ]
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${F5_SECRET_NAME}-*"
    },
    {
      "Sid": "BedrockAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
      ]
    }
  ]
}
EOF
    
    # Create or update policy
    POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/aws-ops-agent-policy"
    
    if aws iam get-policy --policy-arn "$POLICY_ARN" &> /dev/null; then
        print_warning "Policy aws-ops-agent-policy already exists, creating new version"
        aws iam create-policy-version \
            --policy-arn "$POLICY_ARN" \
            --policy-document file://temp-permissions-policy.json \
            --set-as-default
    else
        aws iam create-policy \
            --policy-name aws-ops-agent-policy \
            --policy-document file://temp-permissions-policy.json \
            --description "Custom policy for AWS Operations Agent" \
            --tags Key=Application,Value=aws-ops-agent Key=ManagedBy,Value=CLI
    fi
    
    # Attach custom policy to role
    aws iam attach-role-policy \
        --role-name aws-ops-agent-execution-role \
        --policy-arn "$POLICY_ARN"
    
    # Clean up temporary file
    rm -f temp-permissions-policy.json
    
    print_info "IAM roles and policies deployed successfully"
}

# Get deployment outputs
get_outputs() {
    print_step "Getting deployment outputs..."
    
    if [ "$DEPLOYMENT_METHOD" = "cloudformation" ]; then
        # Get CloudFormation outputs
        LAMBDA_ROLE_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`LambdaExecutionRoleArn`].OutputValue' \
            --output text)
        
        GLOBAL_READER_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`GlobalReaderRoleArn`].OutputValue' \
            --output text)
    else
        # Get role ARNs directly
        LAMBDA_ROLE_ARN=$(aws iam get-role \
            --role-name aws-ops-agent-execution-role \
            --query 'Role.Arn' \
            --output text)
        
        GLOBAL_READER_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/${GLOBAL_READER_ROLE_NAME}"
    fi
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  IAM Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Created Resources:"
    echo "  🔐 Lambda Execution Role: aws-ops-agent-execution-role"
    echo "  🔐 Lambda Execution Role ARN: $LAMBDA_ROLE_ARN"
    echo "  🔐 Global Reader Role: $GLOBAL_READER_ROLE_NAME"
    echo "  🔐 Global Reader Role ARN: $GLOBAL_READER_ARN"
    echo ""
    echo "Next Steps:"
    echo "  1. Deploy Lambda function using the execution role ARN"
    echo "  2. Set up cross-account trust relationships for Global Reader role"
    echo "  3. Create F5 API credentials secret in Secrets Manager"
    echo "  4. Test role assumption and permissions"
    echo ""
    echo "Environment Variables for Lambda:"
    echo "  SSO_ROLE_ARN=$GLOBAL_READER_ARN"
    echo "  F5_SECRET_NAME=$F5_SECRET_NAME"
    echo "  CORE_NETWORK_ACCOUNT_ID=$CORE_NETWORK_ACCOUNT_ID"
    echo "  WORKLOAD_ACCOUNT_IDS=$WORKLOAD_ACCOUNT_IDS"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy IAM roles and policies for AWS Operations Agent"
    echo ""
    echo "Options:"
    echo "  -m, --method METHOD     Deployment method: cloudformation or cli (default: cloudformation)"
    echo "  -s, --stack-name NAME   CloudFormation stack name (default: aws-ops-agent-iam)"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Required Environment Variables:"
    echo "  CORE_NETWORK_ACCOUNT_ID    AWS Account ID for Core Network resources"
    echo "  WORKLOAD_ACCOUNT_IDS       Comma-separated list of Workload Account IDs"
    echo ""
    echo "Optional Environment Variables:"
    echo "  GLOBAL_READER_ROLE_NAME    Name of SSO Global Reader Role (default: GlobalReaderRole)"
    echo "  F5_SECRET_NAME            Name of F5 API credentials secret (default: f5-distributed-cloud-api-credentials)"
    echo ""
    echo "Examples:"
    echo "  # Deploy using CloudFormation (recommended)"
    echo "  export CORE_NETWORK_ACCOUNT_ID=111111111111"
    echo "  export WORKLOAD_ACCOUNT_IDS=222222222222,333333333333"
    echo "  $0"
    echo ""
    echo "  # Deploy using AWS CLI"
    echo "  export CORE_NETWORK_ACCOUNT_ID=111111111111"
    echo "  export WORKLOAD_ACCOUNT_IDS=222222222222,333333333333"
    echo "  $0 --method cli"
    echo ""
}

# Parse command line arguments
DEPLOYMENT_METHOD="cloudformation"

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--method)
            DEPLOYMENT_METHOD="$2"
            shift 2
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
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

# Validate deployment method
if [[ "$DEPLOYMENT_METHOD" != "cloudformation" && "$DEPLOYMENT_METHOD" != "cli" ]]; then
    print_error "Invalid deployment method: $DEPLOYMENT_METHOD"
    print_info "Valid methods: cloudformation, cli"
    exit 1
fi

# Main execution
main() {
    echo ""
    print_info "AWS Operations Agent - IAM Deployment"
    echo ""
    
    check_prerequisites
    display_config
    
    if [ "$DEPLOYMENT_METHOD" = "cloudformation" ]; then
        deploy_cloudformation
    else
        deploy_cli
    fi
    
    get_outputs
}

# Run main function
main "$@"