# AWS CLI Tool Design - 讓 AI Agent 自己構建 AWS 命令

## 🎯 問題

當前的 `elb_tool.py` 有限制：
- ❌ 只有預定義的功能（query_load_balancer, describe_load_balancer_listeners）
- ❌ 想查詢 listener rules 需要修改代碼添加新函數
- ❌ 每次新需求都要寫新的 Python 函數
- ❌ 不靈活，無法處理臨時查詢需求

## 💡 解決方案：通用 AWS CLI Tool

類似 workflow automation 的 CLI Tool，給 AI Agent 一個通用的 AWS CLI 執行工具，讓它根據需求自己構建命令。

## 🏗️ 架構設計

### 方案 1: AWS CLI Command Tool（推薦）

```python
@tool
def execute_aws_cli_command(
    service: str,
    operation: str,
    parameters: Dict[str, Any],
    credential_manager,
    account_id: Optional[str] = None,
    request_id: str = 'unknown'
) -> Dict[str, Any]:
    """
    Execute AWS CLI command dynamically.
    
    This tool allows the AI agent to query ANY AWS service without 
    pre-defined functions. The agent can construct queries based on 
    AWS CLI documentation.
    
    Args:
        service: AWS service name (e.g., 'elbv2', 'ec2', 'route53')
        operation: API operation (e.g., 'describe-listeners', 'describe-rules')
        parameters: Dictionary of parameters for the operation
        credential_manager: CredentialManager instance
        account_id: AWS account ID (optional)
        request_id: Request ID for logging
        
    Returns:
        Dictionary containing the AWS API response
        
    Examples:
        # Query listener rules
        service='elbv2'
        operation='describe-rules'
        parameters={'ListenerArn': 'arn:aws:...'}
        
        # Query target health
        service='elbv2'
        operation='describe-target-health'
        parameters={'TargetGroupArn': 'arn:aws:...'}
        
        # Query EC2 instances
        service='ec2'
        operation='describe-instances'
        parameters={'Filters': [{'Name': 'tag:Name', 'Values': ['web-*']}]}
    """
```

### 方案 2: Boto3 Dynamic Tool

```python
@tool
def query_aws_resource(
    service: str,
    method: str,
    params: Dict[str, Any],
    credential_manager,
    account_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query AWS resources dynamically using boto3.
    
    The AI agent can call ANY boto3 method on ANY AWS service.
    
    Args:
        service: Boto3 service name (e.g., 'elbv2', 'ec2', 'rds')
        method: Boto3 method name (e.g., 'describe_listeners', 'describe_rules')
        params: Method parameters as dictionary
        credential_manager: CredentialManager instance
        account_id: AWS account ID (optional)
        
    Returns:
        Dictionary containing the boto3 response
    """
```

## 📋 實現方案

### 完整實現：aws_cli_tool.py

```python
"""
AWS CLI Tool for AWS Operations Agent.

This module provides a universal AWS CLI tool that allows the AI agent
to query ANY AWS service without pre-defined functions.
"""

import json
import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from botocore.exceptions import ClientError, ParamValidationError
from datetime import datetime

logger = logging.getLogger(__name__)


@tool
def execute_aws_cli_command(
    service: str,
    operation: str,
    parameters: Dict[str, Any],
    credential_manager,
    account_id: Optional[str] = None,
    request_id: str = 'unknown'
) -> Dict[str, Any]:
    """
    Execute AWS CLI command dynamically.
    
    This tool allows querying ANY AWS service operation. The AI agent can
    construct queries based on AWS CLI/boto3 documentation.
    
    IMPORTANT: This is a powerful tool. The AI agent should:
    - Use AWS CLI/boto3 documentation to construct correct parameters
    - Validate parameters before calling
    - Handle pagination for large result sets
    - Parse and format results appropriately
    
    Args:
        service: AWS service name (e.g., 'elbv2', 'ec2', 'route53', 'rds')
        operation: API operation in snake_case (e.g., 'describe_listeners', 'describe_rules')
        parameters: Dictionary of parameters for the operation
        credential_manager: CredentialManager instance
        account_id: AWS account ID (optional, defaults to CORE_NETWORK_ACCOUNT_ID)
        request_id: Request ID for logging
        
    Returns:
        Dictionary containing:
            - success: bool
            - service: str
            - operation: str
            - result: dict (AWS API response)
            - error: str (if error occurred)
            
    Examples:
        # Query ELB listener rules
        service='elbv2'
        operation='describe_rules'
        parameters={'ListenerArn': 'arn:aws:elasticloadbalancing:...'}
        
        # Query target health
        service='elbv2'
        operation='describe_target_health'
        parameters={'TargetGroupArn': 'arn:aws:elasticloadbalancing:...'}
        
        # Query EC2 instances by tag
        service='ec2'
        operation='describe_instances'
        parameters={'Filters': [{'Name': 'tag:Name', 'Values': ['web-*']}]}
        
        # Query RDS instances
        service='rds'
        operation='describe_db_instances'
        parameters={'DBInstanceIdentifier': 'my-database'}
    """
    start_time = datetime.utcnow()
    
    try:
        from src.agent.cloudwatch_logger import cloudwatch_logger
        
        logger.info(f"Executing AWS CLI command: {service}.{operation}")
        logger.info(f"Parameters: {json.dumps(parameters, default=str)}")
        
        # Normalize account_id
        target_account = account_id
        if not target_account or target_account == 'CORE_NETWORK_ACCOUNT_ID':
            import os
            target_account = os.environ.get('CORE_NETWORK_ACCOUNT_ID')
        
        # Get boto3 client for the service
        try:
            client = credential_manager.get_boto3_client(
                service,
                account_id=target_account
            )
        except Exception as e:
            error_msg = f"Failed to create {service} client: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg
            }
        
        # Get the operation method
        if not hasattr(client, operation):
            error_msg = f"Operation '{operation}' not found in {service} service"
            logger.error(error_msg)
            
            # Suggest similar operations
            available_ops = [op for op in dir(client) if not op.startswith('_')]
            suggestions = [op for op in available_ops if operation.replace('_', '') in op.replace('_', '')]
            
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg,
                "suggestions": suggestions[:5] if suggestions else []
            }
        
        # Execute the operation
        try:
            method = getattr(client, operation)
            response = method(**parameters)
            
            # Remove ResponseMetadata for cleaner output
            if 'ResponseMetadata' in response:
                del response['ResponseMetadata']
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={
                    'service': service,
                    'operation': operation,
                    'account_id': target_account
                },
                execution_time_ms=execution_time_ms,
                success=True,
                request_id=request_id,
                result_summary=f"Successfully executed {service}.{operation}"
            )
            
            logger.info(f"Successfully executed {service}.{operation}")
            
            return {
                "success": True,
                "service": service,
                "operation": operation,
                "account_id": target_account,
                "result": response,
                "execution_time_ms": execution_time_ms
            }
            
        except ParamValidationError as e:
            error_msg = f"Invalid parameters for {service}.{operation}: {str(e)}"
            logger.error(error_msg)
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={'service': service, 'operation': operation},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_msg
            )
            
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": error_msg,
                "hint": "Check AWS CLI/boto3 documentation for correct parameter format"
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            
            logger.error(f"AWS API error: {error_code} - {error_msg}")
            
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={'service': service, 'operation': operation},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=f"{error_code}: {error_msg}"
            )
            
            return {
                "success": False,
                "service": service,
                "operation": operation,
                "error": f"{error_code}: {error_msg}",
                "error_code": error_code
            }
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Error executing AWS CLI command: {error_msg}", exc_info=True)
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        try:
            from src.agent.cloudwatch_logger import cloudwatch_logger
            cloudwatch_logger.log_tool_execution(
                tool_name='execute_aws_cli_command',
                parameters={'service': service, 'operation': operation},
                execution_time_ms=execution_time_ms,
                success=False,
                request_id=request_id,
                error_message=error_msg
            )
        except ImportError:
            pass
        
        return {
            "success": False,
            "service": service,
            "operation": operation,
            "error": error_msg
        }


# Helper function for common ELB queries
def get_listener_rules_helper(listener_arn: str, credential_manager, account_id: Optional[str] = None):
    """Helper function to get listener rules - can be used by AI or directly."""
    return execute_aws_cli_command.func(
        service='elbv2',
        operation='describe_rules',
        parameters={'ListenerArn': listener_arn},
        credential_manager=credential_manager,
        account_id=account_id
    )
```

## 🎯 System Prompt 更新

在 `src/agent/prompts.py` 中添加：

```python
### AWS CLI Tool
- **execute_aws_cli_command**: Execute ANY AWS CLI command dynamically
  - Input: JSON string with `service`, `operation`, `parameters`, optional `account_id`
  - Example: `{"service": "elbv2", "operation": "describe_rules", "parameters": {"ListenerArn": "arn:aws:..."}}`
  - Returns: AWS API response
  - **IMPORTANT**: You can query ANY AWS service operation. Use AWS CLI/boto3 documentation to construct correct parameters.
  - Common services: elbv2, ec2, rds, s3, lambda, dynamodb, route53
  - Common operations: describe_*, list_*, get_*
  
#### Example Queries:
```
# Query listener rules
{"service": "elbv2", "operation": "describe_rules", "parameters": {"ListenerArn": "arn:aws:..."}}

# Query target health
{"service": "elbv2", "operation": "describe_target_health", "parameters": {"TargetGroupArn": "arn:aws:..."}}

# Query EC2 instances
{"service": "ec2", "operation": "describe_instances", "parameters": {"Filters": [{"Name": "tag:Name", "Values": ["web-*"]}]}}

# Query RDS databases
{"service": "rds", "operation": "describe_db_instances", "parameters": {}}

# Query Lambda functions
{"service": "lambda", "operation": "list_functions", "parameters": {}}
```

### AWS Expert Knowledge
You are an AWS expert with deep knowledge of AWS services and their APIs. When users ask about AWS resources:

1. **Identify the AWS service** (e.g., elbv2 for load balancers, ec2 for instances)
2. **Determine the correct operation** (e.g., describe_rules, describe_listeners)
3. **Construct the parameters** based on AWS CLI/boto3 documentation
4. **Use execute_aws_cli_command** to query the resource
5. **Parse and format the results** for the user

You have access to ALL AWS services and operations through execute_aws_cli_command. Don't say "I don't have a tool for that" - you can query anything!
```

## 📊 使用範例

### 範例 1: 查詢 Listener Rules

**User Query**: "Show me the listener rules for ALB my-alb"

**AI Reasoning**:
```
1. First, I need to get the load balancer ARN
2. Then get the listeners
3. Then get the rules for each listener
```

**AI Actions**:
```python
# Step 1: Get load balancer
execute_aws_cli_command(
    service='elbv2',
    operation='describe_load_balancers',
    parameters={'Names': ['my-alb']}
)

# Step 2: Get listeners
execute_aws_cli_command(
    service='elbv2',
    operation='describe_listeners',
    parameters={'LoadBalancerArn': 'arn:aws:...'}
)

# Step 3: Get rules for each listener
execute_aws_cli_command(
    service='elbv2',
    operation='describe_rules',
    parameters={'ListenerArn': 'arn:aws:...'}
)
```

### 範例 2: 查詢 Target Health

**User Query**: "Check the health of targets in target group my-tg"

**AI Actions**:
```python
# Get target group ARN
execute_aws_cli_command(
    service='elbv2',
    operation='describe_target_groups',
    parameters={'Names': ['my-tg']}
)

# Get target health
execute_aws_cli_command(
    service='elbv2',
    operation='describe_target_health',
    parameters={'TargetGroupArn': 'arn:aws:...'}
)
```

### 範例 3: 查詢 EC2 Instances

**User Query**: "Show me all EC2 instances with tag Environment=production"

**AI Actions**:
```python
execute_aws_cli_command(
    service='ec2',
    operation='describe_instances',
    parameters={
        'Filters': [
            {'Name': 'tag:Environment', 'Values': ['production']}
        ]
    }
)
```

## 🔐 安全考慮

### 1. 只讀操作

```python
# 在 tool 中添加操作白名單
ALLOWED_OPERATIONS = [
    'describe_*',
    'list_*',
    'get_*',
    'query_*'
]

# 阻止修改操作
BLOCKED_OPERATIONS = [
    'create_*',
    'delete_*',
    'update_*',
    'modify_*',
    'terminate_*',
    'stop_*',
    'start_*'
]
```

### 2. 操作驗證

```python
def is_operation_allowed(operation: str) -> bool:
    """Check if operation is allowed (read-only)."""
    for pattern in BLOCKED_OPERATIONS:
        if operation.startswith(pattern.replace('*', '')):
            return False
    return True
```

## 🎯 優勢

### vs 預定義函數

| 特性 | 預定義函數 (elb_tool.py) | AWS CLI Tool |
|------|-------------------------|--------------|
| 靈活性 | ❌ 只能做預定義的事 | ✅ 可以做任何 AWS 查詢 |
| 維護成本 | ❌ 每個新功能要寫代碼 | ✅ 不需要修改代碼 |
| 學習曲線 | ✅ 簡單，函數名清晰 | ⚠️ 需要了解 AWS CLI |
| 錯誤處理 | ✅ 針對性錯誤處理 | ⚠️ 通用錯誤處理 |
| 性能 | ✅ 優化過的查詢 | ⚠️ 可能需要多次調用 |
| AI 能力 | ❌ 受限於預定義功能 | ✅ AI 可以自由組合查詢 |

## 🚀 實施步驟

### Step 1: 創建 aws_cli_tool.py

```bash
# 創建新文件
touch src/tools/aws_cli_tool.py
```

### Step 2: 註冊到 Agent Orchestrator

在 `src/agent/agent_orchestrator.py` 中添加：

```python
@tool
def execute_aws_cli_command(params: str) -> str:
    """
    Execute AWS CLI command dynamically.
    Use this to query ANY AWS service operation.
    
    Args:
        params: JSON string with 'service', 'operation', 'parameters', optional 'account_id'
        Example: '{"service": "elbv2", "operation": "describe_rules", "parameters": {"ListenerArn": "arn:aws:..."}}'
    
    Returns:
        JSON string with AWS API response
    """
    from src.tools.aws_cli_tool import execute_aws_cli_command as aws_cli_exec
    try:
        params_dict = json.loads(params) if isinstance(params, str) else params
        result = aws_cli_exec.func(
            service=params_dict['service'],
            operation=params_dict['operation'],
            parameters=params_dict.get('parameters', {}),
            credential_manager=orchestrator.credential_manager,
            account_id=params_dict.get('account_id'),
            request_id=orchestrator._current_request_id
        )
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
```

### Step 3: 更新 System Prompt

在 `src/agent/prompts.py` 中添加 AWS CLI Tool 的說明。

### Step 4: 測試

```bash
# 測試查詢 listener rules
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --payload '{"query": "Show me the listener rules for load balancer my-alb"}' \
  response.json
```

## 📈 未來擴展

### 1. 添加常用查詢模板

```python
QUERY_TEMPLATES = {
    'listener_rules': {
        'service': 'elbv2',
        'operation': 'describe_rules',
        'parameters': {'ListenerArn': '{listener_arn}'}
    },
    'target_health': {
        'service': 'elbv2',
        'operation': 'describe_target_health',
        'parameters': {'TargetGroupArn': '{target_group_arn}'}
    }
}
```

### 2. 添加結果格式化

```python
def format_listener_rules(rules):
    """Format listener rules for better readability."""
    formatted = []
    for rule in rules:
        formatted.append({
            'priority': rule['Priority'],
            'conditions': rule['Conditions'],
            'actions': rule['Actions']
        })
    return formatted
```

### 3. 添加智能建議

```python
def suggest_next_query(current_query, result):
    """Suggest related queries based on current result."""
    if 'ListenerArn' in result:
        return "You can query rules with describe_rules"
    if 'TargetGroupArn' in result:
        return "You can check target health with describe_target_health"
```

---

這個方案讓 AI Agent 擁有查詢**任何** AWS 資源的能力，而不需要每次都修改代碼！
