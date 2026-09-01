# Teams Outgoing Webhook 整合指南

這份文件說明如何將 AWS Ops Agent 與 Microsoft Teams 整合，讓你可以在 Teams Channel 中直接詢問 AI 助手。

## 架構概覽

```
Teams Channel
    ↓ (1) 用戶: @AWSBot 查詢 n8n 的 DNS
    ↓
Outgoing Webhook → API Gateway → Lambda
    ↓ (2) 立即返回: "🔄 處理中..."
    ↓
    ↓ (3) Lambda 異步處理查詢
    ↓
    ↓ (4) 完成後發送結果
    ↓
Incoming Webhook → Teams Channel
    ↓ (5) 顯示: "📍 DNS: n8n-dgt-dev..."
```

## 為什麼需要兩個 Webhook？

| Webhook 類型 | 方向 | 用途 | 限制 |
|-------------|------|------|------|
| **Outgoing Webhook** | Teams → Lambda | 接收用戶問題 | 5 秒 timeout |
| **Incoming Webhook** | Lambda → Teams | 發送查詢結果 | 無 timeout |

由於你的 Lambda 執行時間是 20-60 秒，我們使用異步模式：
1. Outgoing Webhook 立即返回 "處理中..."（< 5 秒）
2. Lambda 在背景執行查詢
3. 完成後透過 Incoming Webhook 發送結果

## 設定步驟

### Step 1: 建立 Teams Incoming Webhook（你做）

這個 webhook 讓 Lambda 可以發送訊息回 Teams。

1. 打開你的 Teams Channel
2. 點擊 Channel 名稱旁的 `...` → `Connectors`
3. 搜尋 "Incoming Webhook"
4. 點擊 `Configure`
5. 設定：
   - Name: `AWSBot Response`
   - Upload image (optional): 可以上傳一個 bot 圖示
6. 點擊 `Create`
7. **複製 Webhook URL**（看起來像這樣）：
   ```
   https://outlook.office.com/webhook/xxxxx/IncomingWebhook/yyyyy/zzzzz
   ```

### Step 2: 更新 Lambda 環境變數

將 Incoming Webhook URL 加入 Lambda 環境變數：

```bash
# 方法 1: 使用 AWS CLI
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --environment Variables="{
    CROSS_ACCOUNT_ROLE_NAME=aws-ops-agent-cross-account-role,
    F5_SECRET_NAME=your-secret-name,
    CORE_NETWORK_ACCOUNT_ID=123456789012,
    WORKLOAD_ACCOUNT_IDS=123456789012,234567890123,
    ATHENA_DATABASE=your-database,
    ATHENA_OUTPUT_BUCKET=your-bucket,
    TEAMS_INCOMING_WEBHOOK_URL=https://outlook.office.com/webhook/xxxxx/IncomingWebhook/yyyyy/zzzzz
  }"

# 方法 2: 使用 CloudFormation
# 在 deployment/aws-ops-agent-complete.yaml 中加入：
# Environment:
#   Variables:
#     TEAMS_INCOMING_WEBHOOK_URL: !Ref TeamsIncomingWebhookUrl
```

或者在 AWS Console 中：
1. 進入 Lambda Console
2. 選擇你的 function: `aws-ops-agent-dev`
3. Configuration → Environment variables
4. 點擊 `Edit`
5. 加入新變數：
   - Key: `TEAMS_INCOMING_WEBHOOK_URL`
   - Value: `<你的 Incoming Webhook URL>`

### Step 3: 部署新的 Lambda Handler

更新 Lambda 使用新的 Teams webhook handler：

```bash
cd deployment

# 重新打包 Lambda
./build_package.sh

# 更新 Lambda function
aws lambda update-function-code \
  --function-name aws-ops-agent-dev \
  --zip-file fileb://aws-ops-agent-function.zip

# 等待更新完成
aws lambda wait function-updated --function-name aws-ops-agent-dev

# 更新 handler 指向新的 Teams handler
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --handler src.teams_webhook_handler.lambda_handler

# 確認更新
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Handler'
```

### Step 4: 取得 API Gateway URL

```bash
# 取得 API Gateway URL
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api-gateway-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text
```

你會得到類似這樣的 URL：
```
https://xxxxxxxxxx.execute-api.ap-southeast-1.amazonaws.com/prod/query
```

### Step 5: 建立 Teams Outgoing Webhook（你做）

這個 webhook 讓 Teams 可以發送訊息給 Lambda。

1. 在 Teams 中，點擊左下角的 `Apps`
2. 搜尋 "Outgoing Webhook"
3. 點擊 `Add to a team`
4. 選擇你的 Channel
5. 設定：
   - Name: `AWSBot`
   - Callback URL: `<你的 API Gateway URL>`（從 Step 4 取得）
   - Description: `AWS Operations AI Assistant`
6. 點擊 `Create`
7. **複製 Security Token**（稍後會用到）

### Step 6: 測試整合

在 Teams Channel 中測試：

```
@AWSBot 查詢 n8n 的 DNS
```

你應該會看到：
1. 立即回應：
   ```
   🔄 正在處理您的查詢...
   
   查詢: 查詢 n8n 的 DNS
   
   請稍候，結果將在處理完成後顯示。
   ```

2. 20-60 秒後，收到結果：
   ```
   🤖 AWSBot 查詢結果
   
   📍 DNS: n8n-dgt-dev.internal.example.com
   ⚖️ ALB: alb-core-net-apse1-dev
   🎯 Targets: 2/4 healthy
   
   ⏱️ 執行時間: 45000ms
   ```

## 進階配置

### 加入 Security Token 驗證（建議）

為了安全，應該驗證 Teams 發送的請求：

1. 在 `src/teams_webhook_handler.py` 中加入驗證：

```python
def verify_teams_signature(event: Dict[str, Any]) -> bool:
    """Verify Teams webhook signature."""
    expected_token = os.environ.get('TEAMS_SECURITY_TOKEN')
    if not expected_token:
        logger.warning("TEAMS_SECURITY_TOKEN not configured")
        return True  # Skip verification if not configured
    
    # Teams sends the token in Authorization header
    headers = event.get('headers', {})
    auth_header = headers.get('Authorization', '')
    
    # Format: "Bearer <token>"
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return token == expected_token
    
    return False
```

2. 在 Lambda 環境變數中加入 `TEAMS_SECURITY_TOKEN`

### 自訂回應格式

你可以修改 `send_teams_message()` 函數來自訂回應格式，例如：

```python
# 加入更多 Adaptive Card 元素
payload["attachments"][0]["content"]["body"].append({
    "type": "FactSet",
    "facts": [
        {"title": "DNS:", "value": "n8n-dgt-dev.internal.example.com"},
        {"title": "ALB:", "value": "alb-core-net-apse1-dev"},
        {"title": "Status:", "value": "✅ Healthy"}
    ]
})
```

### 監控和日誌

查看 Lambda 執行日誌：

```bash
# 查看最近的日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow

# 搜尋特定查詢
aws logs filter-log-events \
  --log-group-name /aws/lambda/aws-ops-agent-dev \
  --filter-pattern "Teams webhook"
```

## 故障排除

### 問題 1: Teams 顯示 "Unable to reach app"

**原因**: API Gateway URL 不正確或 Lambda 沒有回應

**解決**:
```bash
# 測試 API Gateway
curl -X POST https://your-api-gateway-url/query \
  -H "Content-Type: application/json" \
  -d '{"type":"message","text":"test query"}'

# 檢查 Lambda 日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow
```

### 問題 2: 收到 "處理中..." 但沒有最終結果

**原因**: Incoming Webhook URL 不正確或 Lambda 執行失敗

**解決**:
```bash
# 檢查環境變數
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Environment.Variables.TEAMS_INCOMING_WEBHOOK_URL'

# 測試 Incoming Webhook
curl -X POST "https://outlook.office.com/webhook/xxxxx/IncomingWebhook/yyyyy/zzzzz" \
  -H "Content-Type: application/json" \
  -d '{"type":"message","text":"Test message"}'

# 檢查 Lambda 執行日誌
aws logs filter-log-events \
  --log-group-name /aws/lambda/aws-ops-agent-dev \
  --filter-pattern "async processing"
```

### 問題 3: Lambda timeout

**原因**: Lambda 執行時間超過配置的 timeout

**解決**:
```bash
# 增加 Lambda timeout 到 5 分鐘
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --timeout 300

# 檢查當前配置
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Timeout'
```

### 問題 4: 權限錯誤

**原因**: Lambda 沒有權限調用自己（異步模式）

**解決**:
確保 Lambda execution role 有以下權限：
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:*:*:function:aws-ops-agent-dev"
    }
  ]
}
```

## 使用範例

### 查詢 DNS
```
@AWSBot 查詢 n8n 的 DNS
```

### 查詢 ALB 狀態
```
@AWSBot 檢查 alb-core-net 的健康狀態
```

### 查詢 IP 資訊
```
@AWSBot 調查 IP 10.0.1.100
```

### 查詢日誌
```
@AWSBot 查詢 VPC Flow Logs 過去 1 小時
```

## 限制

1. **Outgoing Webhook 限制**:
   - 5 秒 timeout（已透過異步處理解決）
   - 只能在被 @ 提及時觸發
   - 需要在 Channel 中使用，不支援私訊

2. **Incoming Webhook 限制**:
   - 每個 webhook 每秒最多 4 個請求
   - 訊息大小限制 28 KB

3. **Lambda 限制**:
   - 最大執行時間 15 分鐘
   - 記憶體限制（建議至少 512 MB）

## 下一步

- [ ] 加入 Security Token 驗證
- [ ] 自訂 Adaptive Card 格式
- [ ] 加入更多查詢範例
- [ ] 設定 CloudWatch Alarms 監控
- [ ] 考慮使用 Azure Bot Service（更完整的 bot 功能）

## 參考資料

- [Teams Outgoing Webhooks](https://docs.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-outgoing-webhook)
- [Teams Incoming Webhooks](https://docs.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook)
- [Adaptive Cards](https://adaptivecards.io/)
- [AWS Lambda Async Invocation](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html)
