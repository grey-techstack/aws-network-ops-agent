#!/bin/bash
# Optimized build script for AWS Lambda deployment package
# This version minimizes Lambda Layer size by excluding unnecessary dependencies

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
DEPS_HASH_FILE="$BUILD_DIR/.deps_hash"
REUSE_LAYER="false"
CURRENT_DEPS_HASH=""
PIP_CACHE_DIR="${PIP_CACHE_DIR:-$BUILD_DIR/.pip-cache}"

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
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    local python_ver=$(python3 --version | cut -d' ' -f2)
    print_info "Python version: $python_ver"
    
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        exit 1
    fi
    
    if ! command -v zip &> /dev/null; then
        print_error "zip is not installed"
        exit 1
    fi
    
    print_info "All prerequisites satisfied"
}

# Compute requirements hash and decide if we can reuse the existing layer
check_cached_layer() {
    print_step "Checking dependency cache..."

    if [ ! -f "requirements-lambda.txt" ]; then
        print_error "requirements-lambda.txt not found"
        exit 1
    fi

    local current_hash
    current_hash=$(sha256sum requirements-lambda.txt | awk '{print $1}')
    CURRENT_DEPS_HASH="$current_hash"

    if [ -f "$DEPS_HASH_FILE" ] && [ -d "$LAYER_DIR/python" ]; then
        local prev_hash
        prev_hash=$(cat "$DEPS_HASH_FILE" 2>/dev/null || true)
        if [ "$current_hash" = "$prev_hash" ]; then
            REUSE_LAYER="true"
            print_info "Dependencies unchanged; will reuse existing lambda_layer"
        else
            print_info "Dependencies changed; will reinstall"
        fi
    else
        print_info "No cached layer; will install dependencies"
    fi

}

# Clean previous builds
clean_build() {
    print_step "Cleaning previous builds..."
    if [ "$REUSE_LAYER" = "true" ]; then
        # Preserve layer to avoid reinstall; clear function package and zips
        rm -rf "$FUNCTION_DIR" lambda-layer.zip aws-ops-agent-function.zip
        rm -rf "$BUILD_DIR/lambda_package"
        print_info "Preserved existing lambda_layer for reuse"
    else
        rm -rf "$LAYER_DIR" "$FUNCTION_DIR" "$BUILD_DIR/lambda_package"
        rm -f lambda-layer.zip aws-ops-agent-function.zip
        # Keep pip cache between runs to speed up reinstalls
        mkdir -p "$PIP_CACHE_DIR"
    fi
    print_info "Clean complete"
}

# Create build directories
create_directories() {
    print_step "Creating build directories..."
    mkdir -p "$LAYER_DIR/python"
    mkdir -p "$FUNCTION_DIR"
    mkdir -p "$PIP_CACHE_DIR"
    print_info "Directories created"
}

# Install dependencies to layer (OPTIMIZED)
install_dependencies() {
    if [ "$REUSE_LAYER" = "true" ]; then
        print_info "Reusing existing lambda_layer dependencies (skipping install)"
        # Refresh hash file to reflect current requirements snapshot
        echo "$CURRENT_DEPS_HASH" > "$DEPS_HASH_FILE.tmp"
        mv "$DEPS_HASH_FILE.tmp" "$DEPS_HASH_FILE"
        return
    fi

    print_step "Installing OPTIMIZED dependencies to Lambda layer..."
    
    # Use optimized requirements file
    if [ ! -f "requirements-lambda.txt" ]; then
        print_error "requirements-lambda.txt not found"
        exit 1
    fi
    
    print_info "Using requirements-lambda.txt (production dependencies only)"
    
    # Install dependencies for Lambda runtime
    # Allow pip cache reuse for faster rebuilds; honor PIP_CACHE_DIR if set
    pip3 install -r requirements-lambda.txt -t "$LAYER_DIR/python/" \
        --platform manylinux2014_x86_64 \
        --implementation cp \
        --python-version 3.11 \
        --only-binary=:all: \
        --cache-dir "$PIP_CACHE_DIR" \
        --upgrade \
        --quiet || \
    pip3 install -r requirements-lambda.txt -t "$LAYER_DIR/python/" \
        --cache-dir "$PIP_CACHE_DIR" \
        --upgrade \
        --quiet

    # Persist dependency hash for reuse on next build
    echo "$CURRENT_DEPS_HASH" > "$DEPS_HASH_FILE.tmp"
    mv "$DEPS_HASH_FILE.tmp" "$DEPS_HASH_FILE"
    
    # Remove unnecessary files to reduce size
    print_step "Removing unnecessary files to reduce size..."
    
    # Remove test files
    find "$LAYER_DIR/python" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find "$LAYER_DIR/python" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
    
    # Remove __pycache__ and .pyc files
    find "$LAYER_DIR/python" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$LAYER_DIR/python" -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove .dist-info directories (keep only essential metadata)
    find "$LAYER_DIR/python" -type d -name "*.dist-info" -exec rm -rf {}/RECORD {} + 2>/dev/null || true
    
    # Remove documentation files
    find "$LAYER_DIR/python" -type f -name "*.md" -delete 2>/dev/null || true
    find "$LAYER_DIR/python" -type f -name "*.rst" -delete 2>/dev/null || true
    find "$LAYER_DIR/python" -type f -name "*.txt" -delete 2>/dev/null || true
    
    # Remove example files
    find "$LAYER_DIR/python" -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true
    
    # Calculate layer size
    local layer_size_mb=$(du -sm "$LAYER_DIR" | cut -f1)
    local layer_size_human=$(du -sh "$LAYER_DIR" | cut -f1)
    print_info "Layer size: $layer_size_human (${layer_size_mb}MB)"
    
    # Check if size is within Lambda limits
    if [ "$layer_size_mb" -gt 250 ]; then
        print_warning "Layer size (${layer_size_mb}MB) exceeds Lambda limit (250MB unzipped)"
        print_warning "You may need to further optimize dependencies"
    else
        print_info "Layer size is within Lambda limits ✓"
    fi
    
    # Get installed package count
    local pkg_count=$(find "$LAYER_DIR/python" -maxdepth 2 -name "*.dist-info" -type d | wc -l)
    print_info "Installed $pkg_count packages"
}

# Copy source code
copy_source_code() {
    print_step "Copying source code..."
    
    if [ ! -d "../src" ]; then
        print_error "src directory not found in parent directory"
        exit 1
    fi
    
    # Copy source code
    cp -r ../src "$FUNCTION_DIR/"
    
    # Remove __pycache__ and .pyc files
    find "$FUNCTION_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$FUNCTION_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove test files from source
    find "$FUNCTION_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find "$FUNCTION_DIR" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
    
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
    local layer_zip_mb=$(du -sm lambda-layer.zip | cut -f1)
    print_info "Layer package created: lambda-layer.zip ($layer_zip_size, ${layer_zip_mb}MB compressed)"
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
    
    local layer_unzipped_mb=$(du -sm "$BUILD_DIR/lambda_layer" | cut -f1)
    local layer_zipped_mb=$(du -sm lambda-layer.zip | cut -f1)
    
    cat > deployment-summary.txt << EOF
AWS Operations Agent - Deployment Package Summary (OPTIMIZED)
Generated: $(date)

Build Configuration:
  Python Version: $PYTHON_VERSION
  Build Directory: $BUILD_DIR
  Requirements: requirements-lambda.txt (production only)

Packages:
  Lambda Layer: lambda-layer.zip
    - Compressed: ${layer_zipped_mb}MB
    - Uncompressed: ${layer_unzipped_mb}MB
    - Lambda Limit: 250MB unzipped
    - Status: $([ "$layer_unzipped_mb" -le 250 ] && echo "✓ Within limits" || echo "⚠ Exceeds limit")
  
  Lambda Function: aws-ops-agent-function.zip ($(du -sh aws-ops-agent-function.zip | cut -f1))

Lambda Configuration:
  Runtime: python$PYTHON_VERSION
  Handler: src.lambda_handler.lambda_handler (or src.simple_test_handler.lambda_handler)
  Timeout: 300 seconds (5 minutes)
  Memory: 512 MB
  Architecture: x86_64

Optimization Applied:
  ✓ Excluded test dependencies (pytest, hypothesis, moto)
  ✓ Used langchain-core instead of full langchain package
  ✓ Removed test directories
  ✓ Removed documentation files
  ✓ Removed __pycache__ and .pyc files
  ✓ Cleaned .dist-info metadata

Required Environment Variables:
  - SSO_ROLE_ARN
  - F5_SECRET_NAME (for F5 WAF API)
  - CORE_NETWORK_ACCOUNT_ID
  - WORKLOAD_ACCOUNT_IDS

Next Steps:
  1. Upload lambda-layer.zip to S3 deployment bucket
  2. Update CloudFormation stack with new layer
  3. Deploy function code
  4. Test with sample queries

For detailed deployment instructions, see:
  - deployment/README.md
  - deployment/lambda-deployment-guide.md
EOF
    
    print_info "Summary saved to deployment-summary.txt"
}

# Display build results
display_results() {
    local layer_unzipped_mb=$(du -sm "$BUILD_DIR/lambda_layer" | cut -f1)
    local layer_zipped_mb=$(du -sm lambda-layer.zip | cut -f1)
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Build Complete! (OPTIMIZED)${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Packages created:"
    echo "  📦 Lambda layer: lambda-layer.zip"
    echo "     - Compressed: ${layer_zipped_mb}MB"
    echo "     - Uncompressed: ${layer_unzipped_mb}MB"
    if [ "$layer_unzipped_mb" -le 250 ]; then
        echo -e "     - Status: ${GREEN}✓ Within Lambda 250MB limit${NC}"
    else
        echo -e "     - Status: ${RED}⚠ Exceeds Lambda 250MB limit${NC}"
    fi
    echo "  📦 Lambda function: aws-ops-agent-function.zip ($(du -sh aws-ops-agent-function.zip | cut -f1))"
    echo ""
    echo "Optimizations applied:"
    echo "  ✓ Production dependencies only (no test packages)"
    echo "  ✓ Minimal LangChain footprint (langchain-core + langchain-aws)"
    echo "  ✓ Removed test files and documentation"
    echo ""
    echo "Next steps:"
    echo "  1. Upload to S3: aws s3 cp lambda-layer.zip s3://YOUR-BUCKET/"
    echo "  2. Update stack: aws cloudformation update-stack ..."
    echo "  3. Test deployment"
    echo ""
}

# Main execution
main() {
    echo ""
    print_info "AWS Operations Agent - Optimized Lambda Package Builder"
    echo ""
    
    check_prerequisites
    check_cached_layer
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
