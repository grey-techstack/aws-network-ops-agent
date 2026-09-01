#!/bin/bash
# Deployment script for API Gateway using CloudFormation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="${STACK_NAME:-aws-ops-agent-api}"
STAGE_NAME="${STAGE_NAME:-prod}"
ENABLE_API_KEY="${ENABLE_API_KEY:-false}"
ENABLE_CLOUDWATCH_LOGS="${ENABLE_CLOUDWATCH_LOGS:-true}"
API_KEY_NAME="${API_KEY_NAME:-aws-ops-agent-api-key}"

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    print_info "AWS CLI found: $(aws --version)"
}

# Function to check if Lambda function exists
check_lambda_function() {
    local function_name=$1
    
    if aws lambda get-function --function-name "$function_name" &> /dev/null; then
        print_info "Lambda function '$function_name' found"
        return 0
    else
        print_error "Lambda function '$function_name' not found"
        return 1
    fi
}

# Function to get Lambda function ARN
get_lambda_arn() {
    local function_name=$1
    aws lambda get-function \
        --function-name "$function_name" \
        --query 'Configuration.FunctionArn' \
        --output text
}

# Function to deploy CloudFormation stack
deploy_stack() {
    local lambda_arn=$1
    
    print_info "Deploying CloudFormation stack: $STACK_NAME"
    print_info "  Lambda ARN: $lambda_arn"
    print_info "  Stage: $STAGE_NAME"
    print_info "  API Key: $ENABLE_API_KEY"
    print_info "  CloudWatch Logs: $ENABLE_CLOUDWATCH_LOGS"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" &> /dev/null; then
        print_warning "Stack already exists. Updating..."
        
        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body file://api-gateway-cloudformation.yaml \
            --parameters \
                ParameterKey=LambdaFunctionArn,ParameterValue="$lambda_arn" \
                ParameterKey=ApiStageName,ParameterValue="$STAGE_NAME" \
                ParameterKey=EnableApiKey,ParameterValue="$ENABLE_API_KEY" \
                ParameterKey=ApiKeyName,ParameterValue="$API_KEY_NAME" \
                ParameterKey=EnableCloudWatchLogs,ParameterValue="$ENABLE_CLOUDWATCH_LOGS" \
            --capabilities CAPABILITY_IAM
        
        print_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME"
    else
        print_info "Creating new stack..."
        
        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-body file://api-gateway-cloudformation.yaml \
            --parameters \
                ParameterKey=LambdaFunctionArn,ParameterValue="$lambda_arn" \
                ParameterKey=ApiStageName,ParameterValue="$STAGE_NAME" \
                ParameterKey=EnableApiKey,ParameterValue="$ENABLE_API_KEY" \
                ParameterKey=ApiKeyName,ParameterValue="$API_KEY_NAME" \
                ParameterKey=EnableCloudWatchLogs,ParameterValue="$ENABLE_CLOUDWATCH_LOGS" \
            --capabilities CAPABILITY_IAM
        
        print_info "Waiting for stack creation to complete..."
        aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"
    fi
    
    print_info "Stack deployment complete!"
}

# Function to get stack outputs
get_stack_outputs() {
    print_info "Retrieving stack outputs..."
    
    local api_endpoint=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
        --output text)
    
    local api_id=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiId`].OutputValue' \
        --output text)
    
    echo ""
    print_info "=== Deployment Complete ==="
    echo ""
    print_info "API Endpoint: $api_endpoint"
    print_info "API ID: $api_id"
    
    if [ "$ENABLE_API_KEY" = "true" ]; then
        local api_key_id=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' \
            --output text)
        
        print_info "API Key ID: $api_key_id"
        
        # Retrieve API key value
        local api_key_value=$(aws apigateway get-api-key \
            --api-key "$api_key_id" \
            --include-value \
            --query 'value' \
            --output text)
        
        print_info "API Key Value: $api_key_value"
        
        echo ""
        print_info "Test command with API key:"
        echo "curl -X POST $api_endpoint \\"
        echo "  -H \"Content-Type: application/json\" \\"
        echo "  -H \"x-api-key: $api_key_value\" \\"
        echo "  -d '{\"query\": \"Trace demo.example.com\"}'"
    else
        echo ""
        print_info "Test command:"
        echo "curl -X POST $api_endpoint \\"
        echo "  -H \"Content-Type: application/json\" \\"
        echo "  -d '{\"query\": \"Trace demo.example.com\"}'"
    fi
    
    echo ""
}

# Function to test API endpoint
test_api_endpoint() {
    local api_endpoint=$1
    local api_key=$2
    
    print_info "Testing API endpoint..."
    
    local curl_cmd="curl -X POST $api_endpoint -H \"Content-Type: application/json\""
    
    if [ -n "$api_key" ]; then
        curl_cmd="$curl_cmd -H \"x-api-key: $api_key\""
    fi
    
    curl_cmd="$curl_cmd -d '{\"query\": \"test\"}' -s -o /dev/null -w \"%{http_code}\""
    
    local status_code=$(eval $curl_cmd)
    
    if [ "$status_code" = "200" ] || [ "$status_code" = "400" ]; then
        print_info "API endpoint is responding (HTTP $status_code)"
        return 0
    else
        print_warning "API endpoint returned unexpected status code: $status_code"
        return 1
    fi
}

# Main execution
main() {
    print_info "Starting API Gateway deployment..."
    echo ""
    
    # Check prerequisites
    check_aws_cli
    
    # Get Lambda function name from user or environment
    if [ -z "$LAMBDA_FUNCTION_NAME" ]; then
        read -p "Enter Lambda function name [aws-ops-agent]: " LAMBDA_FUNCTION_NAME
        LAMBDA_FUNCTION_NAME=${LAMBDA_FUNCTION_NAME:-aws-ops-agent}
    fi
    
    # Check if Lambda function exists
    if ! check_lambda_function "$LAMBDA_FUNCTION_NAME"; then
        print_error "Please deploy the Lambda function first"
        exit 1
    fi
    
    # Get Lambda ARN
    LAMBDA_ARN=$(get_lambda_arn "$LAMBDA_FUNCTION_NAME")
    print_info "Lambda ARN: $LAMBDA_ARN"
    echo ""
    
    # Deploy stack
    deploy_stack "$LAMBDA_ARN"
    
    # Get and display outputs
    get_stack_outputs
    
    # Optional: Test endpoint
    read -p "Do you want to test the API endpoint? (y/n) [y]: " test_choice
    test_choice=${test_choice:-y}
    
    if [ "$test_choice" = "y" ] || [ "$test_choice" = "Y" ]; then
        api_endpoint=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
            --output text)
        
        if [ "$ENABLE_API_KEY" = "true" ]; then
            api_key_id=$(aws cloudformation describe-stacks \
                --stack-name "$STACK_NAME" \
                --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' \
                --output text)
            
            api_key_value=$(aws apigateway get-api-key \
                --api-key "$api_key_id" \
                --include-value \
                --query 'value' \
                --output text)
            
            test_api_endpoint "$api_endpoint" "$api_key_value"
        else
            test_api_endpoint "$api_endpoint"
        fi
    fi
    
    echo ""
    print_info "Deployment complete!"
}

# Run main function
main "$@"
