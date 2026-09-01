#!/bin/bash

# Backup Lambda configuration before deploying Teams integration
# This creates backups that can be used for rollback if needed

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Lambda Configuration Backup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"
echo -e "${YELLOW}Backup directory: $BACKUP_DIR${NC}"
echo ""

# Step 1: Backup Lambda configuration
echo -e "${YELLOW}Step 1: Backing up Lambda configuration...${NC}"
aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    > "$BACKUP_DIR/lambda-config.json"

HANDLER=$(jq -r '.Handler' "$BACKUP_DIR/lambda-config.json")
RUNTIME=$(jq -r '.Runtime' "$BACKUP_DIR/lambda-config.json")
TIMEOUT=$(jq -r '.Timeout' "$BACKUP_DIR/lambda-config.json")
MEMORY=$(jq -r '.MemorySize' "$BACKUP_DIR/lambda-config.json")

echo -e "${GREEN}✓ Configuration saved${NC}"
echo "  Handler: $HANDLER"
echo "  Runtime: $RUNTIME"
echo "  Timeout: $TIMEOUT seconds"
echo "  Memory: $MEMORY MB"

# Step 2: Backup environment variables
echo ""
echo -e "${YELLOW}Step 2: Backing up environment variables...${NC}"
aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json > "$BACKUP_DIR/env-vars.json"

ENV_COUNT=$(jq 'length' "$BACKUP_DIR/env-vars.json")
echo -e "${GREEN}✓ Environment variables saved${NC}"
echo "  Variables: $ENV_COUNT"

# Step 3: Backup Lambda code
echo ""
echo -e "${YELLOW}Step 3: Backing up Lambda code...${NC}"
CODE_LOCATION=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Code.Location' \
    --output text)

curl -s "$CODE_LOCATION" -o "$BACKUP_DIR/lambda-code.zip"
CODE_SIZE=$(du -sh "$BACKUP_DIR/lambda-code.zip" | cut -f1)
echo -e "${GREEN}✓ Code saved${NC}"
echo "  Size: $CODE_SIZE"

# Step 4: Create Lambda version
echo ""
echo -e "${YELLOW}Step 4: Creating Lambda version...${NC}"
VERSION_INFO=$(aws lambda publish-version \
    --function-name "$FUNCTION_NAME" \
    --description "Backup before Teams integration - $(date)" \
    --region "$REGION")

VERSION=$(echo "$VERSION_INFO" | jq -r '.Version')
echo "$VERSION_INFO" > "$BACKUP_DIR/version-info.json"
echo -e "${GREEN}✓ Version created${NC}"
echo "  Version: $VERSION"

# Step 5: Create restore script
echo ""
echo -e "${YELLOW}Step 5: Creating restore script...${NC}"

cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash
# Auto-generated restore script

set -e

FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"
BACKUP_DIR="$(dirname "$0")"

echo "Restoring Lambda configuration from backup..."

# Restore handler
HANDLER=$(jq -r '.Handler' "$BACKUP_DIR/lambda-config.json")
echo "Restoring handler: $HANDLER"
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --handler "$HANDLER" \
    --region "$REGION" \
    > /dev/null

aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

# Restore environment variables
echo "Restoring environment variables..."
ENV_VARS=$(cat "$BACKUP_DIR/env-vars.json")
echo "{\"Variables\": $ENV_VARS}" > /tmp/lambda-env-vars.json
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment file:///tmp/lambda-env-vars.json \
    --region "$REGION" \
    > /dev/null
rm -f /tmp/lambda-env-vars.json

aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

# Restore code
echo "Restoring code..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$BACKUP_DIR/lambda-code.zip" \
    --region "$REGION" \
    > /dev/null

aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo "✅ Restore complete!"
echo ""
echo "Verify:"
echo "  aws lambda get-function-configuration --function-name $FUNCTION_NAME --query 'Handler'"
EOF

chmod +x "$BACKUP_DIR/restore.sh"
echo -e "${GREEN}✓ Restore script created${NC}"

# Step 6: Create backup summary
echo ""
echo -e "${YELLOW}Step 6: Creating backup summary...${NC}"

cat > "$BACKUP_DIR/README.md" << EOF
# Lambda Backup - $(date)

## Backup Information

- **Function Name**: $FUNCTION_NAME
- **Region**: $REGION
- **Backup Time**: $(date)
- **Handler**: $HANDLER
- **Runtime**: $RUNTIME
- **Timeout**: $TIMEOUT seconds
- **Memory**: $MEMORY MB
- **Version**: $VERSION

## Backup Contents

- \`lambda-config.json\` - Complete Lambda configuration
- \`env-vars.json\` - Environment variables
- \`lambda-code.zip\` - Function code ($CODE_SIZE)
- \`version-info.json\` - Published version information
- \`restore.sh\` - Automated restore script

## How to Restore

### Method 1: Use restore script (Recommended)

\`\`\`bash
cd $BACKUP_DIR
./restore.sh
\`\`\`

### Method 2: Manual restore

\`\`\`bash
# Restore handler
aws lambda update-function-configuration \\
  --function-name $FUNCTION_NAME \\
  --handler $HANDLER \\
  --region $REGION

# Restore environment variables
ENV_VARS=\$(cat env-vars.json)
aws lambda update-function-configuration \\
  --function-name $FUNCTION_NAME \\
  --environment "Variables=\$ENV_VARS" \\
  --region $REGION

# Restore code
aws lambda update-function-code \\
  --function-name $FUNCTION_NAME \\
  --zip-file fileb://lambda-code.zip \\
  --region $REGION
\`\`\`

### Method 3: Restore to specific version

\`\`\`bash
# Update alias to point to backup version
aws lambda update-alias \\
  --function-name $FUNCTION_NAME \\
  --name prod \\
  --function-version $VERSION \\
  --region $REGION
\`\`\`

## Verification

After restore, test the function:

\`\`\`bash
aws lambda invoke \\
  --function-name $FUNCTION_NAME \\
  --cli-binary-format raw-in-base64-out \\
  --payload '{"query": "查詢 n8n 的 DNS"}' \\
  response.json

cat response.json
\`\`\`
EOF

echo -e "${GREEN}✓ Summary created${NC}"

# Display summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Backup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""
echo "Backed up:"
echo "  ✓ Lambda configuration"
echo "  ✓ Environment variables ($ENV_COUNT variables)"
echo "  ✓ Function code ($CODE_SIZE)"
echo "  ✓ Lambda version ($VERSION)"
echo "  ✓ Restore script"
echo ""
echo -e "${YELLOW}To restore from this backup:${NC}"
echo "  cd $BACKUP_DIR"
echo "  ./restore.sh"
echo ""
echo -e "${YELLOW}Or use the quick rollback script:${NC}"
echo "  ./rollback_teams_integration.sh"
echo ""
