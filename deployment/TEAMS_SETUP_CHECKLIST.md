# Teams Integration Setup Checklist

使用這個 checklist 來確保所有步驟都正確完成。

## 📋 前置準備

- [ ] AWS CLI 已安裝並配置
- [ ] Lambda function `aws-ops-agent-dev` 已部署
- [ ] API Gateway 已設定
- [ ] 有 Teams Channel 管理員權限
- [ ] 已 clone 此 repository

## 🔧 Step 1: 建立 Teams Incoming Webhook

- [ ] 打開 Teams Channel
- [ ] 點擊 Channel 名稱旁的 `...`
- [ ] 選擇 `Connectors`
- [ ] 搜尋 "Incoming Webhook"
- [ ] 點擊 `Configure`
- [ ] 設定名稱: `AWSBot Response`
- [ ] (Optional) 上傳 bot 圖示
- [ ] 點擊 `Create`
- [ ] **複製 Webhook URL** 並儲存

```
Webhook URL: _______________________________________________
```

## 🚀 Step 2: 部署 Teams Handler

- [ ] 開啟終端機
- [ ] 切換到 deployment 目錄
  ```bash
  cd deployment
  ```

- [ ] 設定環境變數
  ```bash
  export TEAMS_INCOMING_WEBHOOK_URL='<paste-your-webhook-url-here>'
  ```

- [ ] 執行部署腳本
  ```bash
  ./deploy_teams_webhook.sh
  ```

- [ ] 確認部署成功（看到綠色 ✓）
- [ ] **複製 API Gateway URL** 並儲存

```
API Gateway URL: _______________________________________________
```

## 🤖 Step 3: 建立 Teams Outgoing Webhook

- [ ] 在 Teams 中，點擊左下角的 `Apps`
- [ ] 搜尋 "Outgoing Webhook"
- [ ] 點擊 `Add to a team`
- [ ] 選擇你的 Channel
- [ ] 設定：
  - [ ] Name: `AWSBot`
  - [ ] Callback URL: `<paste-api-gateway-url-here>`
  - [ ] Description: `AWS Operations AI Assistant`
- [ ] 點擊 `Create`
- [ ] **複製 Security Token** 並儲存（optional）

```
Security Token: _______________________________________________
```

## ✅ Step 4: 測試整合

- [ ] 執行測試腳本
  ```bash
  ./test_teams_webhook.sh
  ```

- [ ] 確認所有測試通過

- [ ] 在 Teams Channel 中測試
  ```
  @AWSBot test
  ```

- [ ] 確認收到 "處理中..." 訊息（< 5 秒）
- [ ] 確認收到最終結果（20-60 秒後）

## 🔐 Step 5: 安全設定（建議）

- [ ] 加入 Security Token 驗證
  ```bash
  export TEAMS_SECURITY_TOKEN='<your-security-token>'
  
  aws lambda update-function-configuration \
    --function-name aws-ops-agent-dev \
    --environment Variables="{...,TEAMS_SECURITY_TOKEN=$TEAMS_SECURITY_TOKEN}"
  ```

- [ ] 設定 API Gateway IP 白名單（optional）
- [ ] 將 Webhook URL 移到 Secrets Manager（optional）

## 📊 Step 6: 監控設定

- [ ] 設定 CloudWatch Alarms
  ```bash
  # Lambda 錯誤告警
  aws cloudwatch put-metric-alarm \
    --alarm-name aws-ops-agent-teams-errors \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=aws-ops-agent-dev
  ```

- [ ] 設定 CloudWatch Dashboard（optional）
- [ ] 測試告警通知

## 🧪 Step 7: 功能測試

測試以下查詢類型：

- [ ] DNS 查詢
  ```
  @AWSBot 查詢 n8n 的 DNS
  ```

- [ ] ALB 狀態
  ```
  @AWSBot 檢查 alb-core-net 的健康狀態
  ```

- [ ] IP 調查
  ```
  @AWSBot 調查 IP 10.0.1.100
  ```

- [ ] 日誌查詢
  ```
  @AWSBot 查詢 VPC Flow Logs 過去 1 小時
  ```

## 📝 Step 8: 文件記錄

- [ ] 記錄 Webhook URLs
- [ ] 記錄 Security Token
- [ ] 更新團隊文件
- [ ] 分享使用指南給團隊成員

## 🎯 驗證清單

確認以下項目都正常運作：

### Lambda Function
- [ ] Handler 設定為 `src.teams_webhook_handler.lambda_handler`
- [ ] 環境變數 `TEAMS_INCOMING_WEBHOOK_URL` 已設定
- [ ] Timeout 設定為至少 300 秒（5 分鐘）
- [ ] Memory 設定為至少 512 MB
- [ ] 有自調用權限（LambdaSelfInvokePolicy）

### API Gateway
- [ ] Endpoint 可以從外部存取
- [ ] CORS 已正確設定
- [ ] 與 Lambda 整合正常

### Teams Webhooks
- [ ] Outgoing Webhook 已建立並啟用
- [ ] Incoming Webhook 可以接收訊息
- [ ] Bot 在 Channel 中可見

### 功能測試
- [ ] 可以在 Teams 中 @ 提及 bot
- [ ] 立即收到 "處理中..." 回應
- [ ] 20-60 秒後收到最終結果
- [ ] 錯誤訊息正確顯示
- [ ] 執行時間顯示正確

## 🐛 故障排除

如果遇到問題，檢查：

### 問題：Teams 顯示 "Unable to reach app"

- [ ] 檢查 API Gateway URL 是否正確
  ```bash
  aws cloudformation describe-stacks \
    --stack-name aws-ops-agent-api-gateway-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue'
  ```

- [ ] 測試 Lambda 是否正常
  ```bash
  aws lambda invoke \
    --function-name aws-ops-agent-dev \
    --payload '{"body":"{}"}' \
    response.json
  ```

- [ ] 查看 Lambda 日誌
  ```bash
  aws logs tail /aws/lambda/aws-ops-agent-dev --follow
  ```

### 問題：收到 "處理中..." 但沒有最終結果

- [ ] 檢查 Incoming Webhook URL
  ```bash
  aws lambda get-function-configuration \
    --function-name aws-ops-agent-dev \
    --query 'Environment.Variables.TEAMS_INCOMING_WEBHOOK_URL'
  ```

- [ ] 測試 Incoming Webhook
  ```bash
  curl -X POST "$TEAMS_INCOMING_WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"type":"message","text":"Test"}'
  ```

- [ ] 檢查 Lambda 異步執行日誌
  ```bash
  aws logs filter-log-events \
    --log-group-name /aws/lambda/aws-ops-agent-dev \
    --filter-pattern "async processing"
  ```

### 問題：Lambda Timeout

- [ ] 增加 Lambda timeout
  ```bash
  aws lambda update-function-configuration \
    --function-name aws-ops-agent-dev \
    --timeout 300
  ```

- [ ] 檢查 Lambda 執行時間
  ```bash
  aws logs filter-log-events \
    --log-group-name /aws/lambda/aws-ops-agent-dev \
    --filter-pattern "execution_time_ms"
  ```

## 📚 參考資料

完成設定後，參考以下文件：

- [ ] 閱讀 `TEAMS_INTEGRATION_QUICKSTART.md` - 快速開始指南
- [ ] 閱讀 `TEAMS_WEBHOOK_SETUP.md` - 詳細設定指南
- [ ] 查看 `teams-webhook-flow.txt` - 架構流程圖
- [ ] 參考 `.env.teams.example` - 環境變數範例

## ✨ 完成！

恭喜！你已經成功設定 Teams 整合。

現在你可以：
- ✅ 在 Teams Channel 中直接詢問 AWS 問題
- ✅ 獲得即時的基礎設施資訊
- ✅ 與團隊成員分享查詢結果
- ✅ 提高運維效率

---

**設定日期**: _______________

**設定人員**: _______________

**Teams Channel**: _______________

**備註**: 
_______________________________________________
_______________________________________________
_______________________________________________
