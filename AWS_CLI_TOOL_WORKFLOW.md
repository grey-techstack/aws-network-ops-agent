# AWS CLI Tool Workflow

## 🔄 How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                               │
│  "Show me the listener rules for load balancer my-alb"          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI Agent (LLM)                              │
│  - Analyzes query                                                │
│  - Identifies: Need to query ELB listener rules                 │
│  - Decides: Use execute_aws_cli_command tool                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              AI Constructs Tool Parameters                       │
│  {                                                               │
│    "service": "elbv2",                                          │
│    "operation": "describe_rules",                               │
│    "parameters": {                                              │
│      "ListenerArn": "arn:aws:elasticloadbalancing:..."         │
│    }                                                            │
│  }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│           execute_aws_cli_command Tool                           │
│  1. Security Check: Is operation read-only? ✅                  │
│  2. Get boto3 client for service (elbv2)                        │
│  3. Validate operation exists (describe_rules)                  │
│  4. Execute: client.describe_rules(**parameters)                │
│  5. Log to CloudWatch                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS API Response                              │
│  {                                                               │
│    "success": true,                                             │
│    "service": "elbv2",                                          │
│    "operation": "describe_rules",                               │
│    "result": {                                                  │
│      "Rules": [                                                 │
│        {                                                        │
│          "RuleArn": "...",                                      │
│          "Priority": "1",                                       │
│          "Conditions": [...],                                   │
│          "Actions": [...]                                       │
│        }                                                        │
│      ]                                                          │
│    }                                                            │
│  }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              AI Agent Formats Response                           │
│  - Parses the Rules array                                       │
│  - Formats conditions and actions                               │
│  - Creates human-readable output                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    User Response                                 │
│  "Found 3 listener rules for my-alb:                            │
│                                                                  │
│  Rule 1 (Priority: 1):                                          │
│    Condition: Host = api.example.com                            │
│    Action: Forward to target-group-api                          │
│                                                                  │
│  Rule 2 (Priority: 2):                                          │
│    Condition: Path = /admin/*                                   │
│    Action: Forward to target-group-admin                        │
│                                                                  │
│  Rule 3 (Default):                                              │
│    Action: Forward to target-group-default"                     │
└─────────────────────────────────────────────────────────────────┘
```

## 🔐 Security Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   Operation Request                              │
│  operation = "describe_rules"                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              is_operation_allowed() Check                        │
│                                                                  │
│  ✅ Allowed Prefixes:                                           │
│     - describe_*                                                │
│     - list_*                                                    │
│     - get_*                                                     │
│     - query_*                                                   │
│                                                                  │
│  ❌ Blocked Prefixes:                                           │
│     - create_*, delete_*, update_*                              │
│     - modify_*, terminate_*, stop_*                             │
│     - start_*, reboot_*, put_*                                  │
│     - attach_*, detach_*                                        │
│     - associate_*, disassociate_*                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Security Decision                               │
│                                                                  │
│  "describe_rules" starts with "describe_" ✅                    │
│  → ALLOWED, proceed with execution                              │
│                                                                  │
│  "delete_load_balancer" starts with "delete_" ❌               │
│  → BLOCKED, return error                                        │
└─────────────────────────────────────────────────────────────────┘
```

## 🆚 Comparison: Old vs New Approach

### Old Approach (Predefined Functions)

```
User Query: "Show me listener rules"
     │
     ▼
AI Agent: "I don't have a tool for that"
     │
     ▼
Developer: Writes new function in elb_tool.py
     │
     ▼
Developer: Updates agent_orchestrator.py
     │
     ▼
Developer: Updates prompts.py
     │
     ▼
Developer: Deploys new code
     │
     ▼
User: Can now query listener rules
```

**Time**: Hours to days
**Effort**: High (code changes, testing, deployment)
**Flexibility**: Low (only works for this specific query)

### New Approach (AWS CLI Tool)

```
User Query: "Show me listener rules"
     │
     ▼
AI Agent: "I'll use execute_aws_cli_command"
     │
     ▼
AI Agent: Constructs parameters
     │
     ▼
Tool: Executes AWS API call
     │
     ▼
User: Gets results immediately
```

**Time**: Seconds
**Effort**: Zero (AI handles it)
**Flexibility**: High (works for ANY AWS query)

## 🎯 Example Scenarios

### Scenario 1: Query Listener Rules

```
User: "Show me listener rules for ALB my-alb"

AI Reasoning:
1. Need to get load balancer ARN first
2. Then get listeners
3. Then get rules for each listener

AI Actions:
Step 1: execute_aws_cli_command
  service: elbv2
  operation: describe_load_balancers
  parameters: {Names: ['my-alb']}
  
Step 2: execute_aws_cli_command
  service: elbv2
  operation: describe_listeners
  parameters: {LoadBalancerArn: 'arn:aws:...'}
  
Step 3: execute_aws_cli_command
  service: elbv2
  operation: describe_rules
  parameters: {ListenerArn: 'arn:aws:...'}

Result: Complete listener rules with conditions and actions
```

### Scenario 2: Query EC2 Instances

```
User: "Show me all production EC2 instances"

AI Reasoning:
1. Need to query EC2 instances
2. Filter by tag Environment=production

AI Actions:
execute_aws_cli_command
  service: ec2
  operation: describe_instances
  parameters: {
    Filters: [
      {Name: 'tag:Environment', Values: ['production']}
    ]
  }

Result: List of production EC2 instances with details
```

### Scenario 3: Query RDS Databases

```
User: "List all RDS databases"

AI Reasoning:
1. Need to query RDS service
2. Use describe_db_instances operation

AI Actions:
execute_aws_cli_command
  service: rds
  operation: describe_db_instances
  parameters: {}

Result: List of all RDS database instances
```

## 🔄 Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              execute_aws_cli_command Called                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Security Check Failed?                              │
│  operation not in allowed list                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Yes
                         ▼
                    Return Error:
                    "Operation not allowed"
                    
                         │ No
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Service Client Creation Failed?                     │
│  Invalid service name                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ Yes
                         ▼
                    Return Error:
                    "Failed to create client"
                    
                         │ No
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Operation Not Found?                                │
│  Method doesn't exist on client                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │ Yes
                         ▼
                    Return Error:
                    "Operation not found"
                    + Suggestions
                    
                         │ No
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Parameter Validation Failed?                        │
│  Invalid parameters for operation                                │
└────────────────────────┬────────────────────────────────────────┘
                         │ Yes
                         ▼
                    Return Error:
                    "Invalid parameters"
                    + Hint
                    
                         │ No
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              AWS API Error?                                      │
│  AccessDenied, ResourceNotFound, etc.                           │
└────────────────────────┬────────────────────────────────────────┘
                         │ Yes
                         ▼
                    Return Error:
                    AWS error code + message
                    
                         │ No
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Success!                                      │
│  Return result with execution time                               │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Tool Selection Logic

```
User Query
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│              AI Agent Decision Tree                              │
│                                                                  │
│  Is there a dedicated tool for this query?                      │
│  ├─ Yes → Use dedicated tool (faster, optimized)               │
│  │         Examples:                                            │
│  │         - query_route53_records                             │
│  │         - query_f5_load_balancer                            │
│  │         - query_load_balancer                               │
│  │                                                              │
│  └─ No → Use execute_aws_cli_command                           │
│           Examples:                                             │
│           - Listener rules                                      │
│           - EC2 instances                                       │
│           - RDS databases                                       │
│           - Lambda functions                                    │
│           - ECS clusters                                        │
└─────────────────────────────────────────────────────────────────┘
```

## 🎓 AI Learning Process

```
┌─────────────────────────────────────────────────────────────────┐
│              AI Agent Knowledge Base                             │
│                                                                  │
│  System Prompt:                                                 │
│  - AWS service names (elbv2, ec2, rds, etc.)                   │
│  - Common operations (describe_*, list_*, get_*)               │
│  - Parameter structures                                         │
│  - Example queries                                              │
│                                                                  │
│  Tool Documentation:                                            │
│  - execute_aws_cli_command description                         │
│  - Input format (service, operation, parameters)               │
│  - Output format (success, result, error)                      │
│  - Security constraints                                         │
│                                                                  │
│  Examples:                                                      │
│  - Listener rules query                                         │
│  - EC2 instances query                                          │
│  - RDS databases query                                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              AI Reasoning Process                                │
│                                                                  │
│  1. Parse user query                                            │
│  2. Identify AWS service (e.g., "listener rules" → elbv2)      │
│  3. Determine operation (e.g., "rules" → describe_rules)       │
│  4. Construct parameters (e.g., ListenerArn from context)      │
│  5. Call execute_aws_cli_command                               │
│  6. Parse result                                                │
│  7. Format for user                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

**Key Insight**: The AWS CLI Tool transforms the AI agent from a "fixed function caller" to an "AWS expert" that can dynamically query any AWS resource based on its knowledge of AWS services and APIs.
