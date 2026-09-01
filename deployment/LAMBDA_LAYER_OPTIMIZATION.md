# Lambda Layer Size Optimization Guide

## Problem

The Lambda Layer with full dependencies is **283MB unzipped**, which exceeds AWS Lambda's **250MB limit**.

## Root Cause

The original `requirements.txt` includes:
- ❌ Test dependencies (pytest, hypothesis, moto) - **NOT needed in Lambda**
- ❌ Full `langchain` package - **Too large, includes unnecessary components**
- ❌ `langchain-community` - **Not needed for our use case**

## Solution

### 1. Use Optimized Requirements File

Created `requirements-lambda.txt` with **production dependencies only**:

```txt
# Core AWS SDK
boto3>=1.34.0

# LangChain minimal set
langchain-core>=0.3.0      # Core agent functionality
langchain-aws>=0.2.0       # Bedrock support

# Utilities
python-dateutil>=2.8.2
requests>=2.31.0
pydantic>=2.5.0,<3.0.0
```

**Key Changes:**
- ✅ Use `langchain-core` instead of full `langchain` package
- ✅ Exclude test dependencies
- ✅ Exclude `langchain-community` (not needed)

### 2. Use Optimized Build Script

Run the new optimized build script:

```bash
cd deployment
chmod +x build_package_optimized.sh
./build_package_optimized.sh
```

**Optimizations Applied:**
- Removes test directories
- Removes documentation files (*.md, *.rst, *.txt)
- Removes __pycache__ and .pyc files
- Cleans .dist-info metadata
- Uses `--no-cache-dir` to avoid caching issues

### 3. Expected Results

**Before Optimization:**
- Unzipped: 283MB ❌ (exceeds 250MB limit)

**After Optimization:**
- Unzipped: ~150-180MB ✅ (within 250MB limit)
- Compressed: ~40-50MB

## Deployment Steps

### Step 1: Build Optimized Package

```bash
cd deployment
./build_package_optimized.sh
```

### Step 2: Upload to S3

```bash
# Upload layer
aws s3 cp lambda-layer.zip s3://aws-ops-agent-deployment-123456789012-ap-southeast-1/

# Upload function
aws s3 cp aws-ops-agent-function.zip s3://aws-ops-agent-deployment-123456789012-ap-southeast-1/
```

### Step 3: Update CloudFormation Stack

```bash
aws cloudformation update-stack \
  --stack-name aws-ops-agent-dev-lambda \
  --template-body file://aws-ops-agent-lambda-only.yaml \
  --parameters file://cf-parameters-lambda.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### Step 4: Wait for Update

```bash
aws cloudformation wait stack-update-complete \
  --stack-name aws-ops-agent-dev-lambda
```

### Step 5: Test

```bash
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"query": "What tools do you have?"}' \
  response.json

cat response.json
```

## What This Enables

With the optimized Lambda Layer, you can now use the **full LangChain agent** with all 6 tools:

1. ✅ **Route53 Tool** - Query DNS records
2. ✅ **CloudFront Tool** - Query distributions
3. ✅ **ELB Tool** - Query load balancers
4. ✅ **Athena VPC Flow Logs Tool** - Query VPC flow logs
5. ✅ **Athena CloudFront Logs Tool** - Query CloudFront logs
6. ⚠️ **F5 WAF Tool** - Need to implement
7. ⚠️ **IP Investigation Tool** - Need to implement

## Next Steps

After deploying the optimized layer:

1. **Switch handler** from `src.simple_test_handler.lambda_handler` to `src.lambda_handler.lambda_handler`
2. **Implement missing tools**:
   - F5 WAF Tool (uses requests library for F5 API)
   - IP Investigation Tool (uses boto3 for AWS IP ranges)
3. **Test full agent** with natural language queries

## Troubleshooting

### If Layer Still Exceeds 250MB

Try these additional optimizations:

1. **Remove more unnecessary files:**
   ```bash
   # In build script, add:
   find "$LAYER_DIR/python" -name "*.so" -type f -exec strip {} \; 2>/dev/null || true
   ```

2. **Use slim Python packages:**
   - Consider using `boto3-stubs` instead of full boto3 if type hints aren't needed

3. **Split into multiple layers:**
   - Layer 1: LangChain dependencies
   - Layer 2: AWS SDK and utilities
   - Lambda supports up to 5 layers

### If Build Fails

Check Python version compatibility:
```bash
python3 --version  # Should be 3.11
pip3 --version
```

### If Dependencies Are Missing

The optimized requirements might be too minimal. Add back specific packages:
```bash
# Add to requirements-lambda.txt
langchain-community>=0.3.0  # If you need community integrations
```

## Comparison

| Aspect | Original | Optimized |
|--------|----------|-----------|
| Requirements File | requirements.txt | requirements-lambda.txt |
| Test Dependencies | ✅ Included | ❌ Excluded |
| LangChain Package | Full package | Core + AWS only |
| Documentation | ✅ Included | ❌ Removed |
| Test Directories | ✅ Included | ❌ Removed |
| Unzipped Size | 283MB ❌ | ~150-180MB ✅ |
| Within Lambda Limit | ❌ No | ✅ Yes |

## References

- [AWS Lambda Limits](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [LangChain Core](https://python.langchain.com/docs/concepts/architecture/#langchain-core)
