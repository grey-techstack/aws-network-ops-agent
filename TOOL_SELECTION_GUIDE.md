# Tool Selection Guide - 工具選擇指南 (Updated Strategy)

## 🎯 新的工具策略

AWS Ops Agent 現在採用 **"通用優先"** 策略：
- **1 個通用工具** (AWS CLI Tool) - **優先使用**
- **13 個專用工具** - **備用/特殊場景**

## 📋 工具選擇決策樹 (新策略)

```
用戶查詢
    ↓
是 AWS 服務查詢？
    ↓
  是 → 使用 AWS CLI Tool ✅ (通用、靈活、統一)
    ↓
    成功？
    ↓
  是 → 返回結果 ✅
    ↓
  否 → 嘗試專用工具 (如果有)
    ↓
是 F5 WAF 查詢？
    ↓
  是 → 使用 F5 專用工具 ✅ (F5 不是 AWS 服務)
```

## 🌐 AWS CLI Tool (主要工具 - 優先使用)

### ✅ 優先使用場景 (幾乎所有 AWS 查詢)

**所有 AWS 服務查詢都應該先嘗試 AWS CLI Tool**:
- ✅ ELB/ALB/NLB 查詢
- ✅ EC2 instances 查詢
- ✅ RDS databases 查詢
- ✅ Lambda functions 查詢
- ✅ Route53 DNS 查詢
- ✅ CloudFront distributions 查詢
- ✅ ECS clusters 查詢
- ✅ 任何其他 AWS 服務

### 為什麼優先使用 AWS CLI Tool？

1. **統一性**: 所有 AWS 查詢使用同一個工具
2. **靈活性**: 可以查詢任何 AWS API 操作
3. **簡單性**: AI 不需要選擇工具，直接用 AWS CLI Tool
4. **完整性**: 直接訪問 AWS API，沒有限制

## 🔧 專用工具 (備用 - 只在特殊情況使用)

### F5 WAF (非 AWS 服務 - 必須使用專用工具)
| 查詢類型 | 使用工具 | 原因 |
|---------|---------|------|
| 查詢 F5 LB (by domain) | `query_f5_load_balancer` | F5 不是 AWS 服務 |
| 查詢 F5 LB (by name) | `query_f5_load_balancer_by_name` | F5 不是 AWS 服務 |
| 查詢 origin pool | `query_f5_origin_pool` | F5 不是 AWS 服務 |
| 列出所有 F5 LB | `list_f5_load_balancers` | F5 不是 AWS 服務 |
| 列出 namespaces | `list_f5_namespaces` | F5 不是 AWS 服務 |

### Athena Logs (特殊查詢 - 可使用專用工具)
| 查詢類型 | 使用工具 | 原因 |
|---------|---------|------|
| VPC Flow Logs | `query_vpc_flow_logs` | Athena 查詢優化 |
| CloudFront Logs | `query_cloudfront_logs` | Athena 查詢優化 |

### AWS 服務 (備用 - 優先使用 AWS CLI Tool)
| 查詢類型 | 優先工具 | 備用工具 |
|---------|---------|---------|
| Route53 DNS | `execute_aws_cli_command` | `query_route53_records` |
| ALB/NLB | `execute_aws_cli_command` | `query_load_balancer` |
| CloudFront | `execute_aws_cli_command` | `query_cloudfront_distribution` |

## 🌐 AWS CLI Tool (通用工具)

### 何時使用 AWS CLI Tool

**✅ 使用場景**:
1. **沒有專用工具的服務**
   - EC2 instances
   - RDS databases
   - Lambda functions
   - ECS clusters
   - DynamoDB tables
   - S3 buckets (read-only)
   - 等等...

2. **專用工具不支持的操作**
   - ELB listener rules (describe_rules)
   - Target health details (describe_target_health)
   - 特定的 AWS API 操作

3. **臨時查詢需求**
   - 一次性查詢
   - 探索性查詢
   - 調試用查詢

**❌ 不要使用場景**:
- 有專用工具的常見查詢
- 需要多步驟組合的查詢（專用工具已優化）

## 📊 實際例子 (新策略)

### 例子 1: 查詢 ALB 基本信息
```
用戶: "Show me load balancer details for my-alb"

AI 決策 (新策略):
1. 識別: AWS ELB 服務查詢
2. 選擇: execute_aws_cli_command ✅ (優先使用)
3. 參數: service='elbv2', operation='describe_load_balancers', parameters={'Names': ['my-alb']}
4. 如果失敗: 嘗試 query_load_balancer (備用)

結果: 完整的 ALB 信息
```

### 例子 2: 查詢 Listener Rules
```
用戶: "Show me listener rules for my-alb"

AI 決策 (新策略):
1. 識別: AWS ELB 服務查詢
2. 選擇: execute_aws_cli_command ✅ (優先使用)
3. 步驟:
   - 先查 load balancer ARN
   - 再查 listeners
   - 最後查 rules
4. 參數: service='elbv2', operation='describe_rules'

結果: 詳細的 listener rules
```

### 例子 3: 查詢 EC2 Instances
```
用戶: "Show me all EC2 instances with tag Environment=production"

AI 決策 (新策略):
1. 識別: AWS EC2 服務查詢
2. 選擇: execute_aws_cli_command ✅ (優先使用)
3. 參數: service='ec2', operation='describe_instances', filters=[...]

結果: 符合條件的 EC2 instances
```

### 例子 4: 查詢 F5 Origin Pool
```
用戶: "Show me origin pool backend servers for lb-app-dev-app-svc-443"

AI 決策 (新策略):
1. 識別: F5 WAF 查詢 (非 AWS 服務)
2. 選擇: query_f5_origin_pool ✅ (F5 專用工具)
3. 原因: F5 不是 AWS 服務，必須用專用工具

結果: Origin servers 的 IP/DNS、port、health check
```

### 例子 5: 查詢 Route53 DNS
```
用戶: "Show me DNS records for demo.example.com"

AI 決策 (新策略):
1. 識別: AWS Route53 服務查詢
2. 選擇: execute_aws_cli_command ✅ (優先使用)
3. 步驟:
   - 先查 hosted zones
   - 再查 records
4. 如果需要 FQDN 匹配: 使用 query_route53_records (備用)

結果: DNS 記錄
```

## 🎓 AI 學習指導 (新策略)

System Prompt 中的指導：

```
**ALWAYS try execute_aws_cli_command FIRST** for ALL AWS queries:
- It's universal and can query ANY AWS service
- It gives you full control over AWS API calls
- It's flexible for any query type

**Use specialized tools ONLY when execute_aws_cli_command fails or is insufficient**:
- query_route53_records - If you need FQDN-based DNS lookup
- query_f5_load_balancer - For F5 Distributed Cloud WAF (not AWS service)
- query_f5_origin_pool - For F5 origin pool details (not AWS service)
- list_f5_load_balancers - For F5 load balancer listing (not AWS service)
- query_cloudfront_distribution - If you need domain-based CloudFront lookup
- query_vpc_flow_logs - For Athena-based VPC flow log queries
- query_cloudfront_logs - For Athena-based CloudFront log queries
```

## 📈 工具使用統計 (預期 - 新策略)

### AWS CLI Tool (預期 80-90% 使用率)
- 所有 AWS 服務查詢 - 高頻使用
- ELB/ALB queries - 高頻使用
- EC2 queries - 中頻使用
- RDS queries - 低頻使用
- Lambda queries - 低頻使用
- Route53 queries - 中頻使用
- CloudFront queries - 低頻使用

### 專用工具 (預期 10-20% 使用率)
- F5 WAF tools - 中頻使用 (非 AWS 服務)
- Athena log tools - 低頻使用 (特殊查詢)
- 其他 AWS 專用工具 - 極低頻使用 (備用)

## 🔍 如何驗證工具選擇

### 部署後檢查
```bash
# 查看哪些工具被調用
aws logs tail /aws/lambda/aws-ops-agent-dev --follow | grep "tool_name"

# 查看 AWS CLI Tool 使用情況
aws logs tail /aws/lambda/aws-ops-agent-dev --follow | grep "execute_aws_cli_command"

# 查看專用工具使用情況
aws logs tail /aws/lambda/aws-ops-agent-dev --follow | grep "query_load_balancer"
```

### 測試查詢
```bash
# Test 1: 應該使用 query_load_balancer
aws lambda invoke --function-name aws-ops-agent-dev \
  --payload '{"query": "Show me load balancer details for my-alb"}' \
  response.json

# Test 2: 應該使用 execute_aws_cli_command
aws lambda invoke --function-name aws-ops-agent-dev \
  --payload '{"query": "Show me listener rules for my-alb"}' \
  response.json

# Test 3: 應該使用 execute_aws_cli_command
aws lambda invoke --function-name aws-ops-agent-dev \
  --payload '{"query": "List all EC2 instances"}' \
  response.json
```

## 💡 最佳實踐

### 對於用戶
1. **常見查詢**: 直接問，AI 會選擇最優工具
2. **特殊查詢**: 說明具體需求，AI 會選擇合適工具
3. **不確定**: 讓 AI 決定，它會根據 prompt 指導選擇

### 對於開發者
1. **監控工具使用**: 看 AI 是否選擇正確
2. **調整 prompt**: 如果 AI 選擇錯誤，改進指導
3. **添加專用工具**: 如果某個查詢頻繁使用 AWS CLI Tool，考慮添加專用工具

### 對於 AI Agent
1. **優先專用工具**: 它們更快、更優化
2. **AWS CLI Tool 作為後備**: 當沒有專用工具時使用
3. **記錄決策**: 在 thinking 中說明為什麼選擇某個工具

## 🎯 總結 (新策略)

### 工具優先級策略
- ✅ **AWS CLI Tool**: 處理 80-90% 的 AWS 查詢（統一、靈活、通用）
- ✅ **F5 專用工具**: 處理所有 F5 WAF 查詢（非 AWS 服務）
- ✅ **其他專用工具**: 10-20% 的特殊場景（備用、優化）
- ✅ **明確指導**: System prompt 告訴 AI 優先使用 AWS CLI Tool

### 優勢
1. **統一性**: 所有 AWS 查詢使用同一個工具
2. **簡單性**: AI 不需要複雜的工具選擇邏輯
3. **靈活性**: 可以查詢任何 AWS API 操作
4. **可維護性**: 減少專用工具的維護負擔
5. **用戶體驗**: 統一的查詢方式，更可預測

### 何時使用專用工具
1. **F5 WAF**: 必須使用（非 AWS 服務）
2. **Athena Logs**: 可選使用（特殊優化）
3. **AWS 服務**: 只在 AWS CLI Tool 失敗時使用（備用）

---

**結論**: AWS CLI Tool 優先策略讓查詢更統一、更簡單、更靈活。專用工具作為備用方案。
