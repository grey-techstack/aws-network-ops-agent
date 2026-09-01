# AWS CLI Tool - Quick Reference Card

## 🚀 Quick Deploy
```bash
cd deployment
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"
bash quick_update_teams.sh
```

## 🧪 Quick Test
```bash
aws lambda invoke --function-name aws-ops-agent-dev \
  --payload '{"query": "Show me listener rules for load balancer my-alb"}' \
  response.json && cat response.json | jq '.body' | jq -r '.'
```

## 📋 Tool Signature
```python
execute_aws_cli_command(
    service: str,           # AWS service (e.g., 'elbv2', 'ec2', 'rds')
    operation: str,         # Operation (e.g., 'describe_rules', 'list_functions')
    parameters: dict,       # Operation parameters
    account_id: str = None  # Optional AWS account ID
)
```

## 🎯 Common Examples

### ELBv2 - Listener Rules
```json
{
  "service": "elbv2",
  "operation": "describe_rules",
  "parameters": {"ListenerArn": "arn:aws:..."}
}
```

### ELBv2 - Target Health
```json
{
  "service": "elbv2",
  "operation": "describe_target_health",
  "parameters": {"TargetGroupArn": "arn:aws:..."}
}
```

### EC2 - Instances by Tag
```json
{
  "service": "ec2",
  "operation": "describe_instances",
  "parameters": {
    "Filters": [{"Name": "tag:Environment", "Values": ["production"]}]
  }
}
```

### RDS - List Databases
```json
{
  "service": "rds",
  "operation": "describe_db_instances",
  "parameters": {}
}
```

### Lambda - List Functions
```json
{
  "service": "lambda",
  "operation": "list_functions",
  "parameters": {}
}
```

### ECS - List Clusters
```json
{
  "service": "ecs",
  "operation": "list_clusters",
  "parameters": {}
}
```

## 🔐 Security Rules

### ✅ Allowed Operations
- `describe_*` - Describe resources
- `list_*` - List resources
- `get_*` - Get details
- `query_*` - Query resources

### ❌ Blocked Operations
- `create_*`, `delete_*`, `update_*`, `modify_*`
- `terminate_*`, `stop_*`, `start_*`, `reboot_*`
- `put_*`, `attach_*`, `detach_*`
- `associate_*`, `disassociate_*`

## 📊 Response Format

### Success
```json
{
  "success": true,
  "service": "elbv2",
  "operation": "describe_rules",
  "account_id": "123456789012",
  "result": { /* AWS API response */ },
  "execution_time_ms": 1234
}
```

### Error
```json
{
  "success": false,
  "service": "elbv2",
  "operation": "describe_rules",
  "error": "Error message",
  "error_code": "ResourceNotFound",
  "suggestions": ["similar_operation_1", "similar_operation_2"]
}
```

## 🔍 Troubleshooting

### Check Logs
```bash
aws logs tail /aws/lambda/aws-ops-agent-dev --follow
```

### Check Tool Usage
```bash
aws logs tail /aws/lambda/aws-ops-agent-dev --since 5m | grep "execute_aws_cli_command"
```

### Check Errors
```bash
aws logs tail /aws/lambda/aws-ops-agent-dev --since 5m | grep ERROR
```

## 🔄 Rollback
```bash
# 1. Restore backup
cp src/tools/elb_tool.py.backup src/tools/elb_tool.py

# 2. Remove tool from agent_orchestrator.py (manual edit)

# 3. Revert prompts.py (manual edit)

# 4. Redeploy
cd deployment && bash quick_update_teams.sh
```

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `AWS_CLI_TOOL_DESIGN.md` | Design & architecture |
| `AWS_CLI_TOOL_IMPLEMENTATION.md` | Implementation details |
| `AWS_CLI_TOOL_WORKFLOW.md` | Visual workflows |
| `DEPLOY_AWS_CLI_TOOL.md` | Deployment guide |
| `AWS_CLI_TOOL_COMPLETE.md` | Complete summary |
| `AWS_CLI_TOOL_QUICK_REFERENCE.md` | This card |

## 🎯 AWS Services Supported

All AWS services with boto3 support:
- ✅ ELBv2 (Load Balancers)
- ✅ EC2 (Instances, Security Groups, VPCs)
- ✅ RDS (Databases, Clusters)
- ✅ Lambda (Functions, Layers)
- ✅ ECS (Clusters, Services, Tasks)
- ✅ S3 (Buckets, Objects - read-only)
- ✅ DynamoDB (Tables, Items - read-only)
- ✅ CloudWatch (Alarms, Metrics)
- ✅ SNS (Topics, Subscriptions)
- ✅ SQS (Queues, Messages)
- ✅ IAM (Roles, Policies - read-only)
- ✅ Route53 (Zones, Records)
- ✅ CloudFront (Distributions)
- ✅ And 200+ more AWS services!

## 💡 Pro Tips

1. **Use dedicated tools first**: They're optimized for common queries
2. **Use AWS CLI Tool for**: Ad-hoc queries, new services, detailed queries
3. **Check AWS docs**: For correct parameter format
4. **Monitor logs**: To see how AI uses the tool
5. **Iterate prompts**: Add examples if AI struggles

## 📞 Quick Help

**Issue**: Tool not found
**Fix**: Check Lambda logs, verify deployment

**Issue**: Operation not allowed
**Fix**: Expected for write operations (security)

**Issue**: Invalid parameters
**Fix**: Check AWS CLI/boto3 documentation

**Issue**: AWS API error
**Fix**: Check IAM permissions, resource exists

---

**Deploy**: `cd deployment && bash quick_update_teams.sh`
**Test**: `aws lambda invoke --function-name aws-ops-agent-dev --payload '{"query": "test"}' response.json`
**Monitor**: `aws logs tail /aws/lambda/aws-ops-agent-dev --follow`
