# AWS Operations Agent - 部署資源清單

## 📋 將會創建的 AWS 資源

部署腳本會在您的 AWS 帳戶中創建以下資源：

---

## 1. Lambda 函數和層

### Lambda Function
- **名稱**: `aws-ops-agent-prod` (或 `aws-ops-agent-{environment}`)
- **Runtime**: Python 3.11
- **Memory**: 512 MB (可配置)
- **Timeout**: 300 秒 (5 分鐘，可配置)
- **用途**: 運行 AI 代理，處理用戶查詢
- **預估費用**: $0.20 每百萬次請求 + 執行時間費用

### Lambda Layer
- **名稱**: `aws-ops-agent-dependencies-prod`
- **內容**: LangChain, boto3, 和其他 Python 依賴
- **大小**: 約 50-100 MB
- **用途**: 減少 Lambda 函數包大小，加快部署
- **預估費用**: 存儲費用約 $0.01/月

---

## 2. IAM 角色和策略

### Lambda Execution Role
- **名稱**: `aws-ops-agent-lambda-execution-role-prod`
- **用途**: Lambda 函數的執行角色
- **權限**:
  - CloudWatch Logs (寫入日誌)
  - STS AssumeRole (跨帳戶訪問)
  - Secrets Manager (讀取 F5 credentials)
  - Athena (查詢日誌)
  - S3 (Athena 查詢結果)
  - Route53 (DNS 查詢)
  - CloudFront (分發查詢)
  - ELB (負載均衡器查詢)
  - EC2 (網絡信息)

### Managed Policies
- **名稱**: `aws-ops-agent-lambda-policy-prod`
- **類型**: Customer Managed Policy
- **用途**: 定義 Lambda 函數的具體權限

### Trust Relationships
- Lambda 服務可以 assume 此角色
- 允許跨帳戶訪問（如果配置）

---

## 3. API Gateway

### REST API
- **名稱**: `aws-ops-agent-api-prod`
- **類型**: REST API (非 HTTP API)
- **端點**: Regional
- **用途**: 提供 HTTP 接口給用戶查詢

### API Resources
- **路徑**: `/query`
- **方法**: POST
- **集成**: Lambda Proxy Integration

### API Stage
- **名稱**: `prod` (或您配置的環境)
- **部署**: 自動部署
- **日誌**: CloudWatch Logs 啟用
- **預估費用**: $3.50 每百萬次請求

### API Key (可選)
- **名稱**: `aws-ops-agent-api-key-prod`
- **用途**: API 認證
- **使用**: 如果 `ENABLE_API_KEY=true`

### Usage Plan (如果啟用 API Key)
- **名稱**: `aws-ops-agent-usage-plan-prod`
- **限制**: 可配置請求速率和配額

---

## 4. S3 存儲桶

### Deployment Bucket
- **名稱**: `aws-ops-agent-deployment-{account-id}-{region}`
- **用途**: 存儲 Lambda 部署包和層
- **內容**:
  - `lambda-layer.zip` (約 50-100 MB)
  - `aws-ops-agent-function.zip` (約 1-5 MB)
- **版本控制**: 啟用
- **預估費用**: $0.023/GB/月 (約 $0.01-0.05/月)

### Athena Output Bucket
- **名稱**: `aws-ops-agent-athena-results-{account-id}-{region}`
- **用途**: 存儲 Athena 查詢結果
- **生命週期**: 建議設置 30 天自動刪除
- **預估費用**: 取決於查詢量，約 $0.01-0.10/月

---

## 5. Secrets Manager

### F5 API Credentials Secret
- **名稱**: `f5-distributed-cloud-api-credentials`
- **內容**: 
  ```json
  {
    "api_url": "https://example.console.example.io/api",
    "api_token": "your-f5-api-token",
    "namespace": "system"
  }
  ```
- **加密**: AWS KMS 加密
- **輪換**: 可選配置自動輪換
- **預估費用**: $0.40/月 per secret

---

## 6. CloudWatch Logs

### Lambda Function Logs
- **Log Group**: `/aws/lambda/aws-ops-agent-prod`
- **保留期**: 7 天 (可配置)
- **用途**: Lambda 函數執行日誌
- **預估費用**: $0.50/GB 存儲 + $0.50/GB 數據傳輸

### API Gateway Logs
- **Log Group**: `/aws/apigateway/aws-ops-agent-api-prod`
- **保留期**: 7 天 (可配置)
- **用途**: API Gateway 訪問日誌
- **預估費用**: $0.50/GB

---

## 7. CloudFormation Stack

### Stack
- **名稱**: `aws-ops-agent-complete`
- **用途**: 管理所有資源的生命週期
- **優點**: 
  - 一鍵部署和刪除
  - 資源依賴管理
  - 回滾支持
- **費用**: 免費

---

## 📊 資源總覽表

| 資源類型 | 數量 | 名稱模式 | 主要用途 |
|---------|------|---------|---------|
| Lambda Function | 1 | `aws-ops-agent-{env}` | AI 代理執行 |
| Lambda Layer | 1 | `aws-ops-agent-dependencies-{env}` | 依賴包 |
| IAM Role | 1 | `aws-ops-agent-lambda-execution-role-{env}` | Lambda 權限 |
| IAM Policy | 1-2 | `aws-ops-agent-lambda-policy-{env}` | 權限定義 |
| API Gateway | 1 | `aws-ops-agent-api-{env}` | HTTP 接口 |
| API Key | 0-1 | `aws-ops-agent-api-key-{env}` | API 認證 |
| S3 Bucket | 2 | `aws-ops-agent-*-{account}-{region}` | 存儲 |
| Secret | 1 | `f5-distributed-cloud-api-credentials` | F5 憑證 |
| Log Group | 2 | `/aws/lambda/*`, `/aws/apigateway/*` | 日誌 |
| CloudFormation Stack | 1 | `aws-ops-agent-complete` | 資源管理 |

**總計**: 約 11-13 個資源

---

## 💰 預估月度費用

基於中等使用量（每天 100 次查詢）：

| 服務 | 預估費用/月 |
|------|------------|
| Lambda 執行 | $5-10 |
| API Gateway | $1-3 |
| S3 存儲 | $0.05-0.15 |
| Secrets Manager | $0.40 |
| CloudWatch Logs | $1-2 |
| Athena 查詢 | $1-5 |
| **總計** | **$8.45-20.55** |

### 費用優化建議：
1. 設置 CloudWatch Logs 保留期為 7 天
2. 設置 Athena 結果自動刪除（30 天）
3. 使用 Lambda 預留容量（如果使用量大）
4. 啟用 API Gateway 緩存（如果查詢重複）

---

## 🗑️ 如何刪除所有資源

### 方法 1：通過 CloudFormation（推薦）

```bash
# 刪除整個堆疊
aws cloudformation delete-stack --stack-name aws-ops-agent-complete

# 等待刪除完成
aws cloudformation wait stack-delete-complete --stack-name aws-ops-agent-complete
```

這會自動刪除所有資源，除了：
- S3 存儲桶（需要先清空）
- CloudWatch Logs（可選保留）

### 方法 2：手動刪除 S3 存儲桶

```bash
# 清空並刪除 deployment bucket
aws s3 rm s3://aws-ops-agent-deployment-{account}-{region} --recursive
aws s3 rb s3://aws-ops-agent-deployment-{account}-{region}

# 清空並刪除 athena bucket
aws s3 rm s3://aws-ops-agent-athena-results-{account}-{region} --recursive
aws s3 rb s3://aws-ops-agent-athena-results-{account}-{region}
```

### 完整清理腳本

```bash
#!/bin/bash
# cleanup.sh - 完整清理所有資源

STACK_NAME="aws-ops-agent-complete"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

echo "清理 AWS Operations Agent 資源..."

# 1. 刪除 CloudFormation 堆疊
echo "刪除 CloudFormation 堆疊..."
aws cloudformation delete-stack --stack-name $STACK_NAME

# 2. 等待堆疊刪除
echo "等待堆疊刪除完成..."
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME

# 3. 清理 S3 存儲桶
echo "清理 S3 存儲桶..."
aws s3 rm s3://aws-ops-agent-deployment-${ACCOUNT_ID}-${REGION} --recursive
aws s3 rb s3://aws-ops-agent-deployment-${ACCOUNT_ID}-${REGION}

aws s3 rm s3://aws-ops-agent-athena-results-${ACCOUNT_ID}-${REGION} --recursive
aws s3 rb s3://aws-ops-agent-athena-results-${ACCOUNT_ID}-${REGION}

# 4. 刪除 CloudWatch Logs（可選）
echo "刪除 CloudWatch Logs..."
aws logs delete-log-group --log-group-name /aws/lambda/aws-ops-agent-prod
aws logs delete-log-group --log-group-name /aws/apigateway/aws-ops-agent-api-prod

echo "清理完成！"
```

---

## 🔒 安全考慮

### 創建的資源的安全特性：

1. **Lambda Function**
   - ✅ 在 VPC 中運行（可選）
   - ✅ 最小權限原則
   - ✅ 環境變數加密

2. **API Gateway**
   - ✅ API Key 認證（可選）
   - ✅ CORS 配置
   - ✅ 請求限流
   - ✅ CloudWatch 日誌

3. **Secrets Manager**
   - ✅ KMS 加密
   - ✅ 自動輪換（可選）
   - ✅ 訪問審計

4. **S3 Buckets**
   - ✅ 版本控制
   - ✅ 加密存儲
   - ✅ 訪問日誌

5. **IAM Roles**
   - ✅ 最小權限
   - ✅ 信任策略限制
   - ✅ 跨帳戶訪問控制

---

## 📝 資源命名規範

所有資源遵循以下命名規範：

```
{project-name}-{resource-type}-{environment}
```

範例：
- `aws-ops-agent-prod` (Lambda Function)
- `aws-ops-agent-api-prod` (API Gateway)
- `aws-ops-agent-lambda-execution-role-prod` (IAM Role)

這使得資源易於識別和管理。

---

## 🔍 監控和維護

### CloudWatch Dashboards（可選創建）
- Lambda 執行指標
- API Gateway 請求指標
- 錯誤率和延遲

### CloudWatch Alarms（建議創建）
- Lambda 錯誤率 > 5%
- API Gateway 5xx 錯誤
- Lambda 執行時間 > 4 分鐘

### 定期維護任務
- 每月檢查 CloudWatch Logs 大小
- 每季度輪換 F5 API Token
- 每半年審查 IAM 權限

---

## ❓ 常見問題

### Q: 這些資源會產生多少費用？
**A**: 基於中等使用量，預計每月 $8-20。主要費用來自 Lambda 執行和 API Gateway 請求。

### Q: 可以在多個區域部署嗎？
**A**: 可以。每個區域會創建獨立的資源集。

### Q: 如何更新已部署的資源？
**A**: 重新運行部署腳本，CloudFormation 會自動更新資源。

### Q: 刪除資源會丟失數據嗎？
**A**: S3 存儲桶中的數據會保留，除非手動刪除。建議在刪除前備份重要數據。

### Q: 可以自定義資源名稱嗎？
**A**: 可以。通過修改 `PROJECT_NAME` 和 `ENVIRONMENT` 環境變數。

---

## 📚 相關文檔

- **部署指南**: `QUICK_START.md`
- **AWS 訪問配置**: `AWS_ACCESS_SETUP.md`
- **F5 API 設置**: `F5_API_SETUP_GUIDE.md`
- **完整部署文檔**: `infrastructure-as-code-guide.md`
