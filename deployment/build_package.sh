#!/bin/bash
# Build script for AWS Lambda deployment package

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
BUILD_DIR="build"
LAYER_DIR="$BUILD_DIR/lambda_layer"
FUNCTION_DIR="$BUILD_DIR/lambda_package"

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
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    local python_ver=$(python3 --version | cut -d' ' -f2)
    print_info "Python version: $python_ver"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        exit 1
    fi
    
    # Check zip
    if ! command -v zip &> /dev/null; then
        print_error "zip is not installed"
        exit 1
    fi
    
    print_info "All prerequisites satisfied"
}

# Clean previous builds
clean_build() {
    print_step "Cleaning previous builds..."
    rm -rf "$BUILD_DIR" *.zip
    print_info "Clean complete"
}

# Create build directories
create_directories() {
    print_step "Creating build directories..."
    mkdir -p "$LAYER_DIR/python"
    mkdir -p "$FUNCTION_DIR"
    print_info "Directories created"
}

# Install dependencies to layer
install_dependencies() {
    print_step "Installing dependencies to Lambda layer..."
    
    # Check if requirements.txt exists
    if [ ! -f "../requirements.txt" ]; then
        print_error "requirements.txt not found in parent directory"
        exit 1
    fi
    
    # Install dependencies for Lambda runtime (Amazon Linux 2 / x86_64)
    pip3 install -r ../requirements.txt -t "$LAYER_DIR/python/" \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.11 \
        --only-binary=:all: \
        --upgrade \
        --quiet || \
    pip3 install -r ../requirements.txt -t "$LAYER_DIR/python/" --upgrade --quiet
    
    # Get installed package count
    local pkg_count=$(find "$LAYER_DIR/python" -maxdepth 1 -type d | wc -l)
    print_info "Installed $pkg_count packages"
    
    # Calculate layer size
    local layer_size=$(du -sh "$LAYER_DIR" | cut -f1)
    print_info "Layer size: $layer_size"
}

# Copy source code
copy_source_code() {
    print_step "Copying source code..."
    
    # Check if src directory exists
    if [ ! -d "../src" ]; then
        print_error "src directory not found in parent directory"
        exit 1
    fi
    
    # Copy source code
    cp -r ../src "$FUNCTION_DIR/"
    
    # Remove __pycache__ and .pyc files
    find "$FUNCTION_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$FUNCTION_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Count Python files
    local py_count=$(find "$FUNCTION_DIR" -name "*.py" | wc -l)
    print_info "Copied $py_count Python files"
}

# Create layer package
create_layer_package() {
    print_step "Creating Lambda layer package..."
    
    cd "$LAYER_DIR"
    zip -r ../../lambda-layer.zip . -q
    cd ../..
    
    local layer_zip_size=$(du -sh lambda-layer.zip | cut -f1)
    print_info "Layer package created: lambda-layer.zip ($layer_zip_size)"
}

# Create function package
create_function_package() {
    print_step "Creating Lambda function package..."
    
    cd "$FUNCTION_DIR"
    zip -r ../../aws-ops-agent-function.zip . -q
    cd ../..
    
    local function_zip_size=$(du -sh aws-ops-agent-function.zip | cut -f1)
    print_info "Function package created: aws-ops-agent-function.zip ($function_zip_size)"
}

# Generate deployment summary
generate_summary() {
    print_step "Generating deployment summary..."
    
    cat > deployment-summary.txt << EOF
AWS Operations Agent - Deployment Package Summary
Generated: $(date)

Build Configuration:
  Python Version: $PYTHON_VERSION
  Build Directory: $BUILD_DIR

Packages:
  Lambda Layer: lambda-layer.zip ($(du -sh lambda-layer.zip | cut -f1))
  Lambda Function: aws-ops-agent-function.zip ($(du -sh aws-ops-agent-function.zip | cut -f1))

Lambda Configuration:
  Runtime: python$PYTHON_VERSION
  Handler: src.lambda_handler.lambda_handler
  Timeout: 300 seconds (5 minutes)
  Memory: 512 MB
  Architecture: x86_64

Required Environment Variables:
  - SSO_ROLE_ARN
  - F5_SECRET_NAME
  - CORE_NETWORK_ACCOUNT_ID
  - WORKLOAD_ACCOUNT_IDS

Next Steps:
  1. Upload lambda-layer.zip as a Lambda layer
  2. Deploy aws-ops-agent-function.zip as Lambda function
  3. Configure environment variables
  4. Set up IAM roles and permissions
  5. Deploy API Gateway

For detailed deployment instructions, see:
  - deployment/README.md
  - deployment/lambda-deployment-guide.md
EOF
    
    print_info "Summary saved to deployment-summary.txt"
}

# Display build results
display_results() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Build Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Packages created:"
    echo "  📦 Lambda layer: lambda-layer.zip ($(du -sh lambda-layer.zip | cut -f1))"
    echo "  📦 Lambda function: aws-ops-agent-function.zip ($(du -sh aws-ops-agent-function.zip | cut -f1))"
    echo ""
    echo "Next steps:"
    echo "  1. Deploy Lambda layer: aws lambda publish-layer-version --layer-name aws-ops-agent-deps --zip-file fileb://lambda-layer.zip"
    echo "  2. Deploy Lambda function: aws lambda create-function --function-name aws-ops-agent --zip-file fileb://aws-ops-agent-function.zip"
    echo "  3. Configure environment variables (see lambda_environment_variables.json)"
    echo "  4. Set up IAM roles (see deployment/iam-roles.yaml)"
    echo ""
    echo "For detailed instructions, see deployment/lambda-deployment-guide.md"
    echo ""
}

# Main execution
main() {
    echo ""
    print_info "AWS Operations Agent - Lambda Package Builder"
    echo ""
    
    check_prerequisites
    clean_build
    create_directories
    install_dependencies
    copy_source_code
    create_layer_package
    create_function_package
    generate_summary
    display_results
}

# Run main function
main "$@"
