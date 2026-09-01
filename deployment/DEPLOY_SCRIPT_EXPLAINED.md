# deploy_teams_webhook.sh 腳本詳解

這個腳本自動化部署 Teams webhook 整合到 AWS Lambda。

## 📋 腳本結構

### 1. 初始化設定

```bash
#!/bin/bash
set -e  # 遇到錯誤立即停止
```

**說明**:
- `#!/bin/bash` - 指定使用 bash shell
- `set -e` - 如果任何命令失敗，立即停止執行（安全機制）

### 2. 顏色定義

```bash
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color
```

**說明**: 定義終端機顏色，讓輸出更易讀
- 紅色：錯誤訊息
- 綠色：成功訊息
- 黃色：步驟標題

### 3. 配置變數

```bash
FUNCTION_NAME="${FUNCTION_NAME:-aws-ops-agent-dev}"
REGION="${AWS_REGION:-ap-southeast-1}"
```

**說明**: 
- `${VARIABLE:-default}` - 如果環境變數未設定，使用預設值
- `FUNCTION_NAME` - Lambda function 名稱（預設：aws-ops-agent-dev）
- `REGION` - AWS 區域（預設：ap-southeast-1）

**自訂方式**:
```bash
export FUNCTION_NAME="my-custom-function"
export AWS_REGION="us-east-1"
./deploy_teams_webhook.sh
```

### 4. 檢查必要環境變數

```bash
if [ -z "$TEAMS_INCOMING_WEBHOOK_URL" ]; then
    echo -e "${RED}Error: TEAMS_INCOMING_WEBHOOK_URL environment variable is required${NC}"
    exit 1
fi
```

**說明**:
- `-z` - 檢查變數是否為空
- 如果未設定 webhook URL，顯示錯誤並退出
- 這是**必要的**環境變數

**使用前必須設定**:
```bash
export TEAMS_INCOMING_WEBHOOK_URL='your-webhook-url'
```

---

## 🔧 部署步驟詳解

### Step 1: 建立 Lambda 套件

```bash
./build_package.sh
```

**做什麼**:
- 執行 `build_package.sh` 腳本
- 打包所有 Python 程式碼和依賴
- 建立 `aws-ops-agent-function.zip`

**輸出**:
```
aws-ops-agent-function.zip (約 50-100 MB)
```

### Step 2: 更新 Lambda 程式碼

```bash
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://aws-ops-agent-function.zip \
    --region "$REGION"
```

**做什麼**:
- 上傳新的 Lambda 程式碼
- `fileb://` - 表示讀取本地二進制文件
- 更新 Lambda function 的程式碼

**AWS 操作**:
- 上傳 zip 檔案到 Lambda
- Lambda 解壓縮並準備新程式碼
- 狀態變為 "Updating"

### Step 3: 等待更新完成

```bash
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"
```

**做什麼**:
- 等待 Lambda 完成程式碼更新
- 確保下一步驟不會在更新中執行
- 避免 "ResourceConflictException" 錯誤

**為什麼需要**:
Lambda 更新是異步的，如果在更新中修改配置會失敗。

### Step 4: 取得現有環境變數

```bash
CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Environment.Variables' \
    --output json)
```

**做什麼**:
- 讀取 Lambda 現有的所有環境變數
- 以 JSON 格式儲存到 `CURRENT_ENV` 變數

**為什麼需要**:
- 保留現有的環境變數（如 F5_SECRET_NAME, ATHENA_DATABASE 等）
- 只新增 TEAMS_INCOMING_WEBHOOK_URL

**範例輸出**:
```json
{
  "CROSS_ACCOUNT_ROLE_NAME": "aws-ops-agent-cross-account-role",
  "F5_SECRET_NAME": "f5-api-credentials",
  "CORE_NETWORK_ACCOUNT_ID": "123456789012",
  ...
}
```

### Step 5: 更新環境變數

```bash
UPDATED_ENV=$(echo "$CURRENT_ENV" | jq --arg url "$TEAMS_INCOMING_WEBHOOK_URL" '. + {TEAMS_INCOMING_WEBHOOK_URL: $url}')

aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment "Variables=$UPDATED_ENV" \
    --region "$REGION"
```

**做什麼**:
1. 使用 `jq` 將新的 webhook URL 加入現有環境變數
2. 更新 Lambda 配置

**jq 命令解釋**:
- `--arg url "$TEAMS_INCOMING_WEBHOOK_URL"` - 傳入 webhook URL
- `. + {TEAMS_INCOMING_WEBHOOK_URL: $url}` - 合併現有變數和新變數

**結果**:
```json
{
  "CROSS_ACCOUNT_ROLE_NAME": "...",
  "F5_SECRET_NAME": "...",
  "TEAMS_INCOMING_WEBHOOK_URL": "https://..."  ← 新增
}
```

### Step 6: 等待配置更新

```bash
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"
```

**做什麼**: 等待環境變數更新完成

### Step 7: 更新 Lambda Handler

```bash
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --handler src.teams_webhook_handler.lambda_handler \
    --region "$REGION"
```

**做什麼**:
- 將 Lambda handler 從 `src.lambda_handler.lambda_handler` 
- 改為 `src.teams_webhook_handler.lambda_handler`

**Handler 格式**:
- `src.teams_webhook_handler` - 模組路徑（檔案：src/teams_webhook_handler.py）
- `.lambda_handler` - 函數名稱

**為什麼需要**:
- 原本的 handler 是標準的 API Gateway handler
- 新的 handler 支援 Teams webhook 和異步處理

### Step 8: 等待 Handler 更新

```bash
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"
```

**做什麼**: 等待 handler 更新完成

### Step 9: 加入自調用權限

這是**最重要**的步驟，讓 Lambda 可以調用自己來實現異步處理。

#### 9.1 取得 Lambda ARN

```bash
LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)
```

**取得**:
```
arn:aws:lambda:ap-southeast-1:123456789012:function:aws-ops-agent-dev
```

#### 9.2 取得 Lambda 執行角色

```bash
ROLE_NAME=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Role' \
    --output text | awk -F'/' '{print $NF}')
```

**做什麼**:
- 取得 Lambda 的 IAM role ARN
- 使用 `awk` 提取 role 名稱（最後一部分）

**範例**:
- 輸入: `arn:aws:iam::123456789012:role/aws-ops-agent-lambda-role`
- 輸出: `aws-ops-agent-lambda-role`

#### 9.3 建立 IAM Policy

```bash
POLICY_DOCUMENT=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "$LAMBDA_ARN"
    }
  ]
}
EOF
)
```

**Policy 說明**:
- **Effect**: Allow - 允許操作
- **Action**: lambda:InvokeFunction - 調用 Lambda 的權限
- **Resource**: Lambda ARN - 只能調用自己

**為什麼需要**:
Lambda 需要這個權限才能在異步模式下調用自己：
```python
lambda_client.invoke(
    FunctionName=function_name,
    InvocationType='Event',  # 異步調用
    Payload=json.dumps(payload)
)
```

#### 9.4 加入或更新 Policy

```bash
if aws iam get-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "$POLICY_NAME" \
    > /dev/null 2>&1; then
    echo "  Policy already exists, updating..."
    aws iam put-role-policy ...
else
    echo "  Creating new policy..."
    aws iam put-role-policy ...
fi
```

**做什麼**:
- 檢查 policy 是否已存在
- 如果存在：更新
- 如果不存在：建立新的

**Policy 名稱**: `LambdaSelfInvokePolicy`

### Step 10: 取得 API Gateway URL

```bash
API_URL=$(aws cloudformation describe-stacks \
    --stack-name aws-ops-agent-api-gateway-dev \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
    --output text)
```

**做什麼**:
- 從 CloudFormation stack 取得 API Gateway URL
- 這個 URL 用於 Teams Outgoing Webhook

**輸出範例**:
```
https://abc123xyz.execute-api.ap-southeast-1.amazonaws.com/prod/query
```

---

## 📊 完整流程圖

```
開始
  ↓
檢查 TEAMS_INCOMING_WEBHOOK_URL
  ↓
Step 1: 建立 Lambda 套件
  ├─ 執行 build_package.sh
  └─ 產生 aws-ops-agent-function.zip
  ↓
Step 2: 上傳程式碼到 Lambda
  ├─ aws lambda update-function-code
  └─ 上傳 zip 檔案
  ↓
Step 3: 等待程式碼更新完成
  └─ aws lambda wait function-updated
  ↓
Step 4: 取得現有環境變數
  ├─ aws lambda get-function-configuration
  └─ 儲存到 CURRENT_ENV
  ↓
Step 5: 加入新環境變數
  ├─ 使用 jq 合併變數
  ├─ 加入 TEAMS_INCOMING_WEBHOOK_URL
  └─ aws lambda update-function-configuration
  ↓
Step 6: 等待配置更新完成
  └─ aws lambda wait function-updated
  ↓
Step 7: 更新 Lambda Handler
  ├─ 改為 src.teams_webhook_handler.lambda_handler
  └─ aws lambda update-function-configuration
  ↓
Step 8: 等待 Handler 更新完成
  └─ aws lambda wait function-updated
  ↓
Step 9: 加入自調用權限
  ├─ 取得 Lambda ARN
  ├─ 取得 IAM Role 名稱
  ├─ 建立 Policy Document
  └─ aws iam put-role-policy
  ↓
Step 10: 取得 API Gateway URL
  └─ aws cloudformation describe-stacks
  ↓
顯示部署結果
  ├─ ✓ Lambda function updated
  ├─ ✓ Handler set
  ├─ ✓ Environment variable configured
  ├─ ✓ Self-invocation permission added
  └─ 顯示 API Gateway URL
  ↓
結束
```

---

## 🔍 關鍵概念

### 1. 為什麼需要等待（wait）？

Lambda 更新是**異步**的：
```
更新請求 → Lambda 開始更新 → 立即返回 → 背景處理
```

如果不等待就執行下一步：
```
❌ 更新程式碼 → 立即更新配置 → 錯誤！(ResourceConflictException)
✅ 更新程式碼 → 等待完成 → 更新配置 → 成功！
```

### 2. 為什麼需要自調用權限？

異步處理流程：
```
Teams → Lambda (Sync)
         ↓ 立即返回 "處理中..."
         ↓ 調用自己 (Async) ← 需要權限！
         ↓
       Lambda (Async)
         ↓ 執行查詢
         ↓ 發送結果到 Teams
```

沒有權限會發生：
```
❌ AccessDeniedException: User is not authorized to perform: lambda:InvokeFunction
```

### 3. 為什麼使用 jq？

保留現有環境變數：
```bash
# 現有變數
{
  "VAR1": "value1",
  "VAR2": "value2"
}

# 使用 jq 合併
. + {TEAMS_INCOMING_WEBHOOK_URL: $url}

# 結果
{
  "VAR1": "value1",      ← 保留
  "VAR2": "value2",      ← 保留
  "TEAMS_INCOMING_WEBHOOK_URL": "..." ← 新增
}
```

如果不用 jq，直接設定會**覆蓋**所有變數：
```bash
❌ --environment Variables={TEAMS_INCOMING_WEBHOOK_URL: "..."}
   結果：VAR1 和 VAR2 都消失了！
```

---

## 🧪 測試腳本

如果想測試腳本但不實際部署，可以加入 `--dry-run` 模式：

```bash
# 在腳本開頭加入
DRY_RUN="${DRY_RUN:-false}"

# 在每個 AWS 命令前加入檢查
if [ "$DRY_RUN" = "true" ]; then
    echo "[DRY RUN] Would execute: aws lambda update-function-code ..."
else
    aws lambda update-function-code ...
fi
```

使用：
```bash
DRY_RUN=true ./deploy_teams_webhook.sh
```

---

## 📝 使用範例

### 基本使用

```bash
export TEAMS_INCOMING_WEBHOOK_URL='https://...'
cd deployment
./deploy_teams_webhook.sh
```

### 自訂 Function 名稱和區域

```bash
export TEAMS_INCOMING_WEBHOOK_URL='https://...'
export FUNCTION_NAME='my-custom-function'
export AWS_REGION='us-east-1'
cd deployment
./deploy_teams_webhook.sh
```

### 使用不同的 AWS Profile

```bash
export AWS_PROFILE='production'
export TEAMS_INCOMING_WEBHOOK_URL='https://...'
cd deployment
./deploy_teams_webhook.sh
```

---

## 🐛 常見錯誤

### 錯誤 1: TEAMS_INCOMING_WEBHOOK_URL not set

```
Error: TEAMS_INCOMING_WEBHOOK_URL environment variable is required
```

**解決**:
```bash
export TEAMS_INCOMING_WEBHOOK_URL='your-webhook-url'
```

### 錯誤 2: Function not found

```
An error occurred (ResourceNotFoundException) when calling the GetFunction operation
```

**原因**: Lambda function 不存在

**解決**:
```bash
# 檢查 function 是否存在
aws lambda list-functions --query 'Functions[].FunctionName'

# 或先部署 Lambda
./deploy_complete_infrastructure.sh
```

### 錯誤 3: Access Denied

```
An error occurred (AccessDeniedException) when calling the UpdateFunctionCode operation
```

**原因**: AWS credentials 沒有權限

**解決**:
```bash
# 檢查當前身份
aws sts get-caller-identity

# 確認有 Lambda 更新權限
aws iam get-user-policy --user-name your-user --policy-name your-policy
```

### 錯誤 4: ResourceConflictException

```
An error occurred (ResourceConflictException) when calling the UpdateFunctionConfiguration operation
```

**原因**: Lambda 正在更新中

**解決**: 腳本已經有 `wait` 命令，如果還是出現，手動等待：
```bash
aws lambda wait function-updated --function-name aws-ops-agent-dev
```

---

## 📚 相關文件

- `build_package.sh` - 建立 Lambda 套件的腳本
- `test_teams_webhook.sh` - 測試部署結果
- `TEAMS_WEBHOOK_SETUP.md` - 完整設定指南
- `READY_TO_DEPLOY.md` - 部署前檢查清單

---

**總結**: 這個腳本自動化了 10 個步驟，確保 Teams webhook 整合正確部署到 Lambda，包括程式碼更新、環境變數設定、handler 更新和權限配置。
