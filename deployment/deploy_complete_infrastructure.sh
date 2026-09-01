#!/bin/bash
# Complete infrastructure deployment script for AWS Operations Agent

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_METHOD="${DEPLOYMENT_METHOD:-cloudformation}"
STACK_NAME="${STACK_NAME:-aws-ops-agent-complete}"
PROJECT_NAME="${PROJECT_NAME:-aws-ops-agent}"
ENVIRONMENT="${ENVIRONMENT:-prod}"

# Required parameters
CORE_NETWORK_ACCOUNT_ID="${CORE_NETWORK_ACCOUNT_ID}"
WORKLOAD_ACCOUNT_IDS="${WORKLOAD_ACCOUNT_IDS}"
F5_API_URL="${F5_API_URL}"
F5_API_TOKEN="${F5_API_TOKEN}"
ATHENA_OUTPUT_BUCKET="${ATHENA_OUTPUT_BUCKET}"
DEPLOYMENT_BUCKET="${DEPLOYMENT_BUCKET}"

# Optional parameters with defaults
GLOBAL_READER_ROLE_NAME="${GLOBAL_READER_ROLE_NAME:-GlobalReaderRole}"
F5_SECRET_NAME="${F5_SECRET_NAME:-f5-distributed-cloud-api-credentials}"
F5_NAMESPACE="${F5_NAMESPACE:-system}"
LAMBDA_TIMEOUT="${LAMBDA_TIMEOUT:-300}"
LAMBDA_MEMORY_SIZE="${LAMBDA_MEMORY_SIZE:-512}"
ATHENA_DATABASE="${ATHENA_DATABASE:-centralized_logging}"
API_STAGE_NAME="${API_STAGE_NAME:-prod}"
ENABLE_API_KEY="${ENABLE_API_KEY:-false}"

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
    
    # Check deployment method specific tools
    if [ "$DEPLOYMENT_METHOD" = "terraform" ]; then
        if ! command -v terraform &> /dev/null; then
            print_error "Terraform is not installed"
            exit 1
        fi
    fi
    
    print_info "All prerequisites satisfied"
}

# Validate required parameters
validate_parameters() {
    print_step "Validating parameters..."
    
    local missing_params=()
    
    # Check required parameters
    [ -z "$CORE_NETWORK_ACCOUNT_ID" ] && missing_params+=("CORE_NETWORK_ACCOUNT_ID")
    [ -z "$WORKLOAD_ACCOUNT_IDS" ] && missing_params+=("WORKLOAD_ACCOUNT_IDS")
    [ -z "$F5_API_URL" ] && missing_params+=("F5_API_URL")
    [ -z "$F5_API_TOKEN" ] && missing_params+=("F5_API_TOKEN")
    [ -z "$ATHENA_OUTPUT_BUCKET" ] && missing_params+=("ATHENA_OUTPUT_BUCKET")
    [ -z "$DEPLOYMENT_BUCKET" ] && missing_params+=("DEPLOYMENT_BUCKET")
    
    if [ ${#missing_params[@]} -ne 0 ]; then
        print_error "Missing required parameters:"
        for param in "${missing_params[@]}"; do
            echo "  - $param"
        done
        echo ""
        show_usage
        exit 1
    fi
    
    # Validate account ID format
    if ! [[ "$CORE_NETWORK_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
        print_error "CORE_NETWORK_ACCOUNT_ID must be a 12-digit AWS Account ID"
        exit 1
    fi
    
    print_info "All parameters validated"
}

# Display configuration
display_config() {
    print_step "Deployment Configuration"
    echo "  Deployment Method: $DEPLOYMENT_METHOD"
    echo "  Stack/Project Name: $STACK_NAME"
    echo "  Environment: $ENVIRONMENT"
    echo "  Core Network Account: $CORE_NETWORK_ACCOUNT_ID"
    echo "  Workload Accounts: $WORKLOAD_ACCOUNT_IDS"
    echo "  F5 API URL: $F5_API_URL"
    echo "  F5 Namespace: $F5_NAMESPACE"
    echo "  Athena Database: $ATHENA_DATABASE"
    echo "  Athena Output Bucket: $ATHENA_OUTPUT_BUCKET"
    echo "  Deployment Bucket: $DEPLOYMENT_BUCKET"
    echo "  Lambda Timeout: ${LAMBDA_TIMEOUT}s"
    echo "  Lambda Memory: ${LAMBDA_MEMORY_SIZE}MB"
    echo "  API Stage: $API_STAGE_NAME"
    echo "  Enable API Key: $ENABLE_API_KEY"
    echo ""
}

# Build deployment packages
build_packages() {
    print_step "Building deployment packages..."
    
    # Run build script
    if [ -f "./build_package.sh" ]; then
        ./build_package.sh
    else
        print_error "build_package.sh not found"
        exit 1
    fi
    
    # Create S3 buckets if they don't exist
    print_info "Checking S3 buckets..."
    
    # Check and create deployment bucket
    if aws s3 ls "s3://$DEPLOYMENT_BUCKET" 2>&1 | grep -q 'NoSuchBucket'; then
        print_info "Creating deployment bucket: $DEPLOYMENT_BUCKET"
        aws s3 mb "s3://$DEPLOYMENT_BUCKET"
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "$DEPLOYMENT_BUCKET" \
            --versioning-configuration Status=Enabled
        
        print_info "Deployment bucket created successfully"
    else
        print_info "Deployment bucket already exists: $DEPLOYMENT_BUCKET"
    fi
    
    # Upload packages to S3
    print_info "Uploading packages to S3..."
    
    aws s3 cp lambda-layer.zip "s3://$DEPLOYMENT_BUCKET/lambda-layer.zip"
    aws s3 cp aws-ops-agent-function.zip "s3://$DEPLOYMENT_BUCKET/aws-ops-agent-function.zip"
    
    print_info "Packages uploaded successfully"
}

# Deploy using CloudFormation
deploy_cloudformation() {
    print_step "Deploying infrastructure using CloudFormation..."
    
    # Create parameters file
    cat > cf-parameters.json << EOF
[
  {
    "ParameterKey": "ProjectName",
    "ParameterValue": "$PROJECT_NAME"
  },
  {
    "ParameterKey": "Environment",
    "ParameterValue": "$ENVIRONMENT"
  },
  {
    "ParameterKey": "GlobalReaderRoleName",
    "ParameterValue": "$GLOBAL_READER_ROLE_NAME"
  },
  {
    "ParameterKey": "CoreNetworkAccountId",
    "ParameterValue": "$CORE_NETWORK_ACCOUNT_ID"
  },
  {
    "ParameterKey": "WorkloadAccountIds",
    "ParameterValue": "$WORKLOAD_ACCOUNT_IDS"
  },
  {
    "ParameterKey": "F5SecretName",
    "ParameterValue": "$F5_SECRET_NAME"
  },
  {
    "ParameterKey": "F5ApiUrl",
    "ParameterValue": "$F5_API_URL"
  },
  {
    "ParameterKey": "F5ApiToken",
    "ParameterValue": "$F5_API_TOKEN"
  },
  {
    "ParameterKey": "F5Namespace",
    "ParameterValue": "$F5_NAMESPACE"
  },
  {
    "ParameterKey": "LambdaTimeout",
    "ParameterValue": "$LAMBDA_TIMEOUT"
  },
  {
    "ParameterKey": "LambdaMemorySize",
    "ParameterValue": "$LAMBDA_MEMORY_SIZE"
  },
  {
    "ParameterKey": "AthenaDatabase",
    "ParameterValue": "$ATHENA_DATABASE"
  },
  {
    "ParameterKey": "AthenaOutputBucket",
    "ParameterValue": "$ATHENA_OUTPUT_BUCKET"
  },
  {
    "ParameterKey": "ApiStageName",
    "ParameterValue": "$API_STAGE_NAME"
  },
  {
    "ParameterKey": "EnableApiKey",
    "ParameterValue": "$ENABLE_API_KEY"
  }
]
EOF
    
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
        --template-body file://aws-ops-agent-complete.yaml \
        --parameters file://cf-parameters.json \
        --capabilities CAPABILITY_NAMED_IAM \
        --tags \
            Key=Application,Value="$PROJECT_NAME" \
            Key=Environment,Value="$ENVIRONMENT" \
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
    
    # Clean up parameters file
    rm -f cf-parameters.json
}

# Deploy using Terraform
deploy_terraform() {
    print_step "Deploying infrastructure using Terraform..."
    
    # Create terraform.tfvars file
    cat > terraform.tfvars << EOF
project_name               = "$PROJECT_NAME"
environment               = "$ENVIRONMENT"
global_reader_role_name   = "$GLOBAL_READER_ROLE_NAME"
core_network_account_id   = "$CORE_NETWORK_ACCOUNT_ID"
workload_account_ids      = [$(echo "$WORKLOAD_ACCOUNT_IDS" | sed 's/,/", "/g' | sed 's/^/"/' | sed 's/$/"/')"]
f5_secret_name           = "$F5_SECRET_NAME"
f5_api_url               = "$F5_API_URL"
f5_api_token             = "$F5_API_TOKEN"
f5_namespace             = "$F5_NAMESPACE"
lambda_timeout           = $LAMBDA_TIMEOUT
lambda_memory_size       = $LAMBDA_MEMORY_SIZE
athena_database          = "$ATHENA_DATABASE"
athena_output_bucket     = "$ATHENA_OUTPUT_BUCKET"
api_stage_name           = "$API_STAGE_NAME"
enable_api_key           = $ENABLE_API_KEY
deployment_bucket        = "$DEPLOYMENT_BUCKET"
EOF
    
    # Initialize Terraform
    terraform init -input=false
    
    # Plan deployment
    print_info "Planning Terraform deployment..."
    terraform plan -var-file="terraform.tfvars" -out=tfplan
    
    # Apply deployment
    print_info "Applying Terraform deployment..."
    terraform apply -input=false tfplan
    
    if [ $? -eq 0 ]; then
        print_info "Terraform deployment completed successfully"
    else
        print_error "Terraform deployment failed"
        exit 1
    fi
    
    # Clean up
    rm -f terraform.tfvars tfplan
}

# Get deployment outputs
get_outputs() {
    print_step "Getting deployment outputs..."
    
    if [ "$DEPLOYMENT_METHOD" = "cloudformation" ]; then
        # Get CloudFormation outputs
        API_URL=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
            --output text)
        
        LAMBDA_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionArn`].OutputValue' \
            --output text)
        
        SECRET_ARN=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`SecretArn`].OutputValue' \
            --output text)
        
        if [ "$ENABLE_API_KEY" = "true" ]; then
            API_KEY_ID=$(aws cloudformation describe-stacks \
                --stack-name "$STACK_NAME" \
                --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' \
                --output text)
        fi
    else
        # Get Terraform outputs
        API_URL=$(terraform output -raw api_gateway_url)
        LAMBDA_ARN=$(terraform output -raw lambda_function_arn)
        SECRET_ARN=$(terraform output -raw secret_arn)
        
        if [ "$ENABLE_API_KEY" = "true" ]; then
            API_KEY_ID=$(terraform output -raw api_key_id)
        fi
    fi
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "🚀 AWS Operations Agent deployed successfully!"
    echo ""
    echo "📋 Deployment Summary:"
    echo "  Environment: $ENVIRONMENT"
    echo "  Lambda Function: $LAMBDA_ARN"
    echo "  API Gateway URL: $API_URL"
    echo "  F5 Secret: $SECRET_ARN"
    
    if [ "$ENABLE_API_KEY" = "true" ] && [ -n "$API_KEY_ID" ]; then
        API_KEY_VALUE=$(aws apigateway get-api-key --api-key "$API_KEY_ID" --include-value --query 'value' --output text)
        echo "  API Key: $API_KEY_VALUE"
    fi
    
    echo ""
    echo "🧪 Test the API:"
    if [ "$ENABLE_API_KEY" = "true" ] && [ -n "$API_KEY_VALUE" ]; then
        echo "  curl -X POST $API_URL \\"
        echo "    -H 'Content-Type: application/json' \\"
        echo "    -H 'x-api-key: $API_KEY_VALUE' \\"
        echo "    -d '{\"query\": \"test\"}'"
    else
        echo "  curl -X POST $API_URL \\"
        echo "    -H 'Content-Type: application/json' \\"
        echo "    -d '{\"query\": \"test\"}'"
    fi
    
    echo ""
    echo "📚 Next Steps:"
    echo "  1. Test the API endpoint with sample queries"
    echo "  2. Set up cross-account trust relationships"
    echo "  3. Configure monitoring and alarms"
    echo "  4. Review CloudWatch logs for any issues"
    echo ""
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy complete AWS Operations Agent infrastructure"
    echo ""
    echo "Options:"
    echo "  -m, --method METHOD     Deployment method: cloudformation or terraform (default: cloudformation)"
    echo "  -s, --stack-name NAME   Stack/project name (default: aws-ops-agent-complete)"
    echo "  -e, --environment ENV   Environment name (default: prod)"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Required Environment Variables:"
    echo "  CORE_NETWORK_ACCOUNT_ID    AWS Account ID for Core Network resources"
    echo "  WORKLOAD_ACCOUNT_IDS       Comma-separated list of Workload Account IDs"
    echo "  F5_API_URL                F5 Distributed Cloud API URL"
    echo "  F5_API_TOKEN              F5 API Token"
    echo "  ATHENA_OUTPUT_BUCKET      S3 bucket for Athena query results"
    echo "  DEPLOYMENT_BUCKET         S3 bucket containing deployment packages"
    echo ""
    echo "Optional Environment Variables:"
    echo "  GLOBAL_READER_ROLE_NAME   Name of SSO Global Reader Role (default: GlobalReaderRole)"
    echo "  F5_SECRET_NAME           Name of F5 API credentials secret (default: f5-distributed-cloud-api-credentials)"
    echo "  F5_NAMESPACE             F5 namespace (default: system)"
    echo "  LAMBDA_TIMEOUT           Lambda timeout in seconds (default: 300)"
    echo "  LAMBDA_MEMORY_SIZE       Lambda memory in MB (default: 512)"
    echo "  ATHENA_DATABASE          Athena database name (default: centralized_logging)"
    echo "  API_STAGE_NAME           API Gateway stage name (default: prod)"
    echo "  ENABLE_API_KEY           Enable API key authentication (default: false)"
    echo ""
    echo "Examples:"
    echo "  # Deploy using CloudFormation"
    echo "  export CORE_NETWORK_ACCOUNT_ID=111111111111"
    echo "  export WORKLOAD_ACCOUNT_IDS=222222222222,333333333333"
    echo "  export F5_API_URL=https://tenant.console.ves.volterra.io/api"
    echo "  export F5_API_TOKEN=your-api-token"
    echo "  export ATHENA_OUTPUT_BUCKET=aws-ops-agent-athena-results-123456789012-us-east-1"
    echo "  export DEPLOYMENT_BUCKET=aws-ops-agent-deployment-123456789012-us-east-1"
    echo "  $0"
    echo ""
    echo "  # Deploy using Terraform"
    echo "  $0 --method terraform"
    echo ""
}

# Parse command line arguments
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
        -e|--environment)
            ENVIRONMENT="$2"
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
if [[ "$DEPLOYMENT_METHOD" != "cloudformation" && "$DEPLOYMENT_METHOD" != "terraform" ]]; then
    print_error "Invalid deployment method: $DEPLOYMENT_METHOD"
    print_info "Valid methods: cloudformation, terraform"
    exit 1
fi

# Main execution
main() {
    echo ""
    print_info "AWS Operations Agent - Complete Infrastructure Deployment"
    echo ""
    
    check_prerequisites
    validate_parameters
    display_config
    
    # Confirm deployment
    read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled"
        exit 0
    fi
    
    build_packages
    
    if [ "$DEPLOYMENT_METHOD" = "cloudformation" ]; then
        deploy_cloudformation
    else
        deploy_terraform
    fi
    
    get_outputs
}

# Run main function
main "$@"