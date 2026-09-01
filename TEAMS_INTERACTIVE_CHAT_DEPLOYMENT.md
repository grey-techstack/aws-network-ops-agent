# Teams Interactive Chat - Deployment Guide

## Overview

This guide walks you through deploying the interactive chat feature for Teams integration.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Existing Lambda function: `aws-ops-agent-dev`
- Teams webhook already configured
- Bash shell (WSL on Windows)

## Deployment Steps

### Step 1: Deploy DynamoDB Table

```bash
cd deployment

# Assume AWS role
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

# Deploy table
bash deploy_teams_session_table.sh dev
```

**Expected Output**:
```
✅ DynamoDB Table Created:
   Table Name: teams-chat-sessions-dev
   Table ARN: arn:aws:dynamodb:ap-southeast-1:123456789012:table/teams-chat-sessions-dev
```

### Step 2: Add DynamoDB Permissions to Lambda Role

```bash
# Get Lambda role name
LAMBDA_ROLE=$(aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Role' \
  --output text | awk -F'/' '{print $NF}')

echo "Lambda Role: $LAMBDA_ROLE"

# Add DynamoDB policy
aws iam put-role-policy \
  --role-name $LAMBDA_ROLE \
  --policy-name DynamoDBTeamsSessions \
  --policy-document file://teams-session-policy.json

echo "✅ DynamoDB permissions added"
```

### Step 3: Update Lambda Environment Variables

```bash
# Add session table name
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --environment "Variables={
    TEAMS_SESSION_TABLE_NAME=teams-chat-sessions-dev,
    CONVERSATION_HISTORY_LIMIT=10,
    SESSION_TTL_HOURS=24,
    TEAMS_INCOMING_WEBHOOK_URL=$(aws lambda get-function-configuration --function-name aws-ops-agent-dev --query 'Environment.Variables.TEAMS_INCOMING_WEBHOOK_URL' --output text),
    F5_SECRET_NAME=$(aws lambda get-function-configuration --function-name aws-ops-agent-dev --query 'Environment.Variables.F5_SECRET_NAME' --output text),
    CORE_NETWORK_ACCOUNT_ID=$(aws lambda get-function-configuration --function-name aws-ops-agent-dev --query 'Environment.Variables.CORE_NETWORK_ACCOUNT_ID' --output text),
    WORKLOAD_ACCOUNT_IDS=$(aws lambda get-function-configuration --function-name aws-ops-agent-dev --query 'Environment.Variables.WORKLOAD_ACCOUNT_IDS' --output text),
    ATHENA_DATABASE=$(aws lambda get-function-configuration --function-name aws-ops-agent-dev --query 'Environment.Variables.ATHENA_DATABASE' --output text),
    ATHENA_OUTPUT_BUCKET=$(aws lambda get-function-configuration --function-name aws-ops-agent-dev --query 'Environment.Variables.ATHENA_OUTPUT_BUCKET' --output text)
  }"

echo "✅ Environment variables updated"
```

**Note**: The above command preserves existing environment variables while adding new ones.

### Step 4: Deploy Updated Lambda Code

The Lambda code needs to be updated to use the session manager. The changes are already in the codebase, so just deploy:

```bash
# Build and deploy
bash quick_update_teams.sh
```

**Expected Output**:
```
✅ Lambda function updated successfully
```

### Step 5: Verify Deployment

```bash
# Check Lambda configuration
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Environment.Variables.TEAMS_SESSION_TABLE_NAME'

# Should output: "teams-chat-sessions-dev"

# Check DynamoDB table
aws dynamodb describe-table \
  --table-name teams-chat-sessions-dev \
  --query 'Table.[TableName,TableStatus,ItemCount]'

# Should output: ["teams-chat-sessions-dev", "ACTIVE", 0]
```

## Testing

### Test 1: Basic Conversation

In Teams:
```
You: @AWSBot trace vision-uat.example.com
Bot: [Shows complete trace]

You: @AWSBot what's the origin pool?
Bot: [Should show origin pool for vision-uat.example.com without asking which domain]
```

### Test 2: Verify Session Storage

```bash
# Check DynamoDB for stored sessions
aws dynamodb scan \
  --table-name teams-chat-sessions-dev \
  --max-items 5

# Should show conversation history
```

### Test 3: Check CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/aws-ops-agent-dev --since 5m --follow

# Look for:
# "Loaded N messages from conversation..."
# "Saved message to session..."
# "Session data: {...}"
```

## Monitoring

### CloudWatch Metrics

Create dashboard to monitor:
- DynamoDB read/write capacity
- Lambda execution time (should increase by ~100-200ms)
- DynamoDB throttling (should be 0)

### CloudWatch Alarms

```bash
# Create alarm for DynamoDB errors
aws cloudwatch put-metric-alarm \
  --alarm-name teams-sessions-dynamodb-errors \
  --alarm-description "Alert on DynamoDB errors" \
  --metric-name UserErrors \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=TableName,Value=teams-chat-sessions-dev
```

## Troubleshooting

### Issue: "Table does not exist"

**Cause**: DynamoDB table not created or wrong table name

**Solution**:
```bash
# Check if table exists
aws dynamodb list-tables | grep teams-chat-sessions

# If not found, redeploy
bash deploy_teams_session_table.sh dev
```

### Issue: "AccessDeniedException" in Lambda logs

**Cause**: Lambda role doesn't have DynamoDB permissions

**Solution**:
```bash
# Reapply IAM policy
aws iam put-role-policy \
  --role-name aws-ops-agent-execution-role-dev \
  --policy-name DynamoDBTeamsSessions \
  --policy-document file://teams-session-policy.json
```

### Issue: Agent doesn't remember context

**Cause**: Session manager not initialized or conversation history not loaded

**Solution**:
```bash
# Check Lambda logs for session manager initialization
aws logs tail /aws/lambda/aws-ops-agent-dev --since 10m | grep "Session manager"

# Should see: "Session manager initialized: table=teams-chat-sessions-dev..."
```

### Issue: Old sessions not being deleted

**Cause**: TTL not enabled on DynamoDB table

**Solution**:
```bash
# Verify TTL is enabled
aws dynamodb describe-time-to-live \
  --table-name teams-chat-sessions-dev

# Should show: "TimeToLiveStatus": "ENABLED"
```

## Rollback

If you need to rollback to one-shot queries:

### Option 1: Feature Flag (Recommended)

Add environment variable to disable session management:
```bash
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --environment Variables={ENABLE_SESSION_MANAGEMENT=false,...}
```

### Option 2: Redeploy Previous Code

```bash
# Restore from backup
cd deployment/backups
# Find latest backup before session feature
ls -lt

# Restore Lambda code
aws lambda update-function-code \
  --function-name aws-ops-agent-dev \
  --zip-file fileb://backup-YYYYMMDD/lambda-code.zip
```

### Option 3: Delete DynamoDB Table (Nuclear Option)

```bash
# This will delete all conversation history
aws cloudformation delete-stack \
  --stack-name teams-chat-sessions-dev

# Remove environment variable
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --environment Variables={...}  # Remove TEAMS_SESSION_TABLE_NAME
```

## Cost Monitoring

### Check DynamoDB Costs

```bash
# Get table metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=teams-chat-sessions-dev \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

**Expected Costs**:
- Storage: ~$0.25/month (1MB)
- Reads: ~$1.25/month (10K reads)
- Writes: ~$1.25/month (1K writes)
- **Total: ~$3/month**

## Maintenance

### Clear Old Sessions Manually

```bash
# List sessions older than 7 days
aws dynamodb scan \
  --table-name teams-chat-sessions-dev \
  --filter-expression "timestamp < :week_ago" \
  --expression-attribute-values "{\":week_ago\":{\"N\":\"$(date -d '7 days ago' +%s)\"}}"

# TTL will auto-delete after 24 hours, but you can manually delete if needed
```

### Backup DynamoDB Table

```bash
# Enable point-in-time recovery (already enabled in template)
aws dynamodb update-continuous-backups \
  --table-name teams-chat-sessions-dev \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Create on-demand backup
aws dynamodb create-backup \
  --table-name teams-chat-sessions-dev \
  --backup-name teams-sessions-backup-$(date +%Y%m%d)
```

## Next Steps

After successful deployment:

1. ✅ Test interactive conversations in Teams
2. ✅ Monitor CloudWatch logs for errors
3. ✅ Check DynamoDB metrics
4. ✅ Gather user feedback
5. ✅ Iterate on context extraction logic

## Support

If you encounter issues:
1. Check CloudWatch logs: `/aws/lambda/aws-ops-agent-dev`
2. Check DynamoDB table status
3. Verify IAM permissions
4. Review this deployment guide

---

**Last Updated**: 2026-02-12
**Status**: Ready for Deployment
**Owner**: AWS Expert Agent Team
