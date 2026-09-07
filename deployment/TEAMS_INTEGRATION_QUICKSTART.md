# Teams 整合快速開始

在 Teams Channel 中使用 AWS Ops Agent 的最快方式。

## 🚀 5 分鐘快速設定

### 前置需求

- ✅ Lambda function 已部署（`aws-ops-agent-dev`）
- ✅ API Gateway 已設定
- ✅ AWS CLI 已配置
- ✅ Teams Channel 管理員權限

### Step 1: 建立 Teams Incoming Webhook（2 分鐘）

1. 打開 Teams Channel → `...` → `Connectors`
2. 搜尋 "Incoming Webhook" → `Configure`
3. Name: `AWSBot Response`
4. `Create` → **複製 URL**

### Step 2: 部署 Teams Handler（2 分鐘）

```bash
cd deployment

# 設定 Incoming Webhook URL
export TEAMS_INCOMING_WEBHOOK_URL='https://outlook.office.com/webhook/xxxxx/...'

# 一鍵部署
./deploy_teams_webhook.sh
```

腳本會自動：
- ✅ 打包 Lambda code
- ✅ 更新 Lambda function
- ✅ 設定環境變數
- ✅ 更新 handler
- ✅ 加入自調用權限
- ✅ 顯示 API Gateway URL

### Step 3: 建立 Teams Outgoing Webhook（1 分鐘）

1. Teams → `Apps` → 搜尋 "Outgoing Webhook"
2. `Add to a team` → 選擇你的 Channel
3. 設定：
   - Name: `AWSBot`
   - Callback URL: **從 Step 2 輸出複製**
   - Description: `AWS Operations AI Assistant`
4. `Create`

### Step 4: 測試（30 秒）

在 Teams Channel 中輸入：

```
@AWSBot 查詢 myapp 的 DNS
```

你會看到：

1. **立即回應**（< 5 秒）：
   ```
   🔄 正在處理您的查詢...
   查詢: 查詢 myapp 的 DNS
   請稍候，結果將在處理完成後顯示。
   ```

2. **最終結果**（20-60 秒後）：
   ```
   🤖 AWSBot 查詢結果
   📍 DNS: myapp-dev.internal.example.com
   ⚖️ ALB: alb-app-dev
   🎯 Targets: 2/4 healthy
   ⏱️ 執行時間: 45000ms
   ```

## 🧪 測試部署

```bash
# 執行完整測試
./test_teams_webhook.sh
```

測試包括：
- ✅ Lambda function 存在
- ✅ Handler 配置正確
- ✅ 環境變數設定
- ✅ 自調用權限
- ✅ Lambda 功能測試
- ✅ API Gateway 測試
- ✅ Incoming Webhook 測試

## 📋 使用範例

### 查詢 DNS
```
@AWSBot 查詢 myapp 的 DNS
@AWSBot 找出 gitlab 的 FQDN
```

### 檢查 ALB
```
@AWSBot 檢查 alb-app 的健康狀態
@AWSBot 查詢 ALB targets
```

### IP 調查
```
@AWSBot 調查 IP 10.0.1.100
@AWSBot 這個 IP 是什麼: 172.16.0.50
```

### 查詢日誌
```
@AWSBot 查詢 VPC Flow Logs 過去 1 小時
@AWSBot 檢查 CloudFront 日誌
```

## 🔧 故障排除

### 問題：Teams 顯示 "Unable to reach app"

```bash
# 檢查 API Gateway
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api-gateway-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue'

# 測試 Lambda
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --payload '{"body":"{}"}' \
  response.json
```

### 問題：沒有收到最終結果

```bash
# 檢查 Incoming Webhook URL
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Environment.Variables.TEAMS_INCOMING_WEBHOOK_URL'

# 查看 Lambda 日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow
```

### 問題：Lambda timeout

```bash
# 增加 timeout 到 5 分鐘
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --timeout 300
```

## 📚 詳細文件

- **完整設定指南**: [TEAMS_WEBHOOK_SETUP.md](./TEAMS_WEBHOOK_SETUP.md)
- **API Gateway 設定**: [API_GATEWAY_SETUP.md](./API_GATEWAY_SETUP.md)
- **Lambda 部署**: [DEPLOYMENT_STEPS.md](./DEPLOYMENT_STEPS.md)

## 🎯 架構說明

```
┌─────────────────────────────────────────────────────────────┐
│                      Teams Channel                          │
│                                                             │
│  👤 User: @AWSBot 查詢 myapp 的 DNS                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ (1) Outgoing Webhook
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                            │
│                  (POST /query)                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ (2) Invoke Lambda
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Lambda Function                           │
│              (teams_webhook_handler)                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Sync Handler                                        │   │
│  │ • Parse Teams payload                               │   │
│  │ • Return "Processing..." (< 5 sec)                  │   │
│  │ • Invoke self asynchronously                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            │ (3) Async Invoke               │
│                            ↓                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Async Handler                                       │   │
│  │ • Initialize Agent                                  │   │
│  │ • Execute query (20-60 sec)                         │   │
│  │ • Format result                                     │   │
│  │ • Send to Teams via Incoming Webhook               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ (4) POST result
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Teams Incoming Webhook                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ (5) Display result
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Teams Channel                          │
│                                                             │
│  🤖 AWSBot:                                                 │
│     📍 DNS: myapp-dev.internal.example.com                   │
│     ⚖️ ALB: alb-app-dev                         │
│     🎯 Targets: 2/4 healthy                                 │
│     ⏱️ 執行時間: 45000ms                                    │
└─────────────────────────────────────────────────────────────┘
```

## 💡 為什麼這樣設計？

### 問題：Teams Outgoing Webhook 有 5 秒 timeout

你的 Lambda 執行時間：20-60 秒 ❌

### 解決方案：異步處理

1. **立即回應**（< 5 秒）：返回 "處理中..."
2. **背景處理**：Lambda 自調用執行查詢
3. **主動推送**：透過 Incoming Webhook 發送結果

### 優點

- ✅ 不受 5 秒限制
- ✅ 用戶體驗好（知道正在處理）
- ✅ 可處理長時間查詢
- ✅ 錯誤處理完善

## 🔐 安全建議

### 1. 加入 Security Token 驗證

```bash
# 在建立 Outgoing Webhook 時會得到 Security Token
export TEAMS_SECURITY_TOKEN='your-security-token'

# 更新 Lambda 環境變數
aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --environment Variables="{...,TEAMS_SECURITY_TOKEN=$TEAMS_SECURITY_TOKEN}"
```

### 2. 限制 API Gateway 存取

在 API Gateway 中加入 IP 白名單（Teams 的 IP 範圍）

### 3. 使用 AWS Secrets Manager

將 Incoming Webhook URL 存在 Secrets Manager：

```bash
# 建立 secret
aws secretsmanager create-secret \
  --name teams-incoming-webhook-url \
  --secret-string "$TEAMS_INCOMING_WEBHOOK_URL"

# 更新 Lambda 從 Secrets Manager 讀取
```

## 📊 監控

### CloudWatch Logs

```bash
# 即時查看日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow

# 搜尋 Teams 相關日誌
aws logs filter-log-events \
  --log-group-name /aws/lambda/aws-ops-agent-dev \
  --filter-pattern "Teams webhook"
```

### CloudWatch Metrics

建議監控：
- Lambda 執行時間
- Lambda 錯誤率
- API Gateway 4xx/5xx 錯誤
- Lambda 並發執行數

### CloudWatch Alarms

```bash
# 建立 Lambda 錯誤告警
aws cloudwatch put-metric-alarm \
  --alarm-name aws-ops-agent-teams-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=aws-ops-agent-dev
```

## 🚀 下一步

### 進階功能

- [ ] 加入 Adaptive Cards 格式化
- [ ] 支援互動式按鈕
- [ ] 加入查詢歷史記錄
- [ ] 多語言支援
- [ ] 自訂回應格式

### 替代方案

如果需要更完整的 bot 功能，考慮：
- **Azure Bot Service**: 完整的 bot 框架
- **AWS Lex**: 對話式 AI
- **Step Functions**: 更複雜的工作流程

## 📞 需要幫助？

- 查看詳細文件：[TEAMS_WEBHOOK_SETUP.md](./TEAMS_WEBHOOK_SETUP.md)
- 執行測試：`./test_teams_webhook.sh`
- 查看日誌：`aws logs tail /aws/lambda/aws-ops-agent-dev --follow`

---

**準備好了嗎？開始設定吧！** 🎉
