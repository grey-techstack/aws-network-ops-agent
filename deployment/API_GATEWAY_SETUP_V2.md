# API Gateway Setup for AWS Ops Agent

## Overview

API Gateway 作為 Lambda 的 HTTP 入口，接收來自 Power Automate 的請求並轉發給 Lambda 執行。

```
Power Automate (Teams) → API Gateway → Lambda → Response
```

## 為什麼用 API Gateway 而不是 Function URL

| 特性 | Function URL | API Gateway |
|------|-------------|-------------|
| 設定複雜度 | 簡單 | 中等 |
| 企業環境相容性 | 可能被 SCP 限制 | 更穩定 |
| 認證方式 | IAM 或 NONE | 多種選項 |
| 成本 | 免費 | 按請求計費 |

在我們的環境中，Function URL 遇到 403 Forbidden 問題（可能是 AWS Organizations SCP 限制），因此改用 API Gateway。

## 當前配置

### API Gateway 資訊

| 項目 | 值 |
|------|-----|
| API 名稱 | aws-ops-agent-api |
| API ID | your-api-id |
| 類型 | HTTP API |
| Region | ap-southeast-1 |
| Stage | prod |
| Endpoint | https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod |

### 路由配置

| Method | Path | Target |
|--------|------|--------|
| POST | / | aws-ops-agent-dev Lambda |

### 認證

- API Gateway 層: 無認證 (AuthorizationType: NONE)
- Lambda 層: API Key 驗證 (在程式碼中檢查 x-api-key header)

## 建立步驟 (CLI)

如需重新建立，執行以下命令：

```bash
# 1. 建立 HTTP API
aws apigatewayv2 create-api \
  --name aws-ops-agent-api \
  --protocol-type HTTP \
  --region ap-southeast-1

# 2. 建立 Integration (連接 Lambda)
aws apigatewayv2 create-integration \
  --api-id <API_ID> \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:ap-southeast-1:123456789012:function:aws-ops-agent-dev \
  --payload-format-version 2.0 \
  --region ap-southeast-1

# 3. 建立 Route
aws apigatewayv2 create-route \
  --api-id <API_ID> \
  --route-key "POST /" \
  --target integrations/<INTEGRATION_ID> \
  --region ap-southeast-1

# 4. 建立 Stage (自動部署)
aws apigatewayv2 create-stage \
  --api-id <API_ID> \
  --stage-name prod \
  --auto-deploy \
  --region ap-southeast-1

# 5. 授權 API Gateway 調用 Lambda
aws lambda add-permission \
  --function-name aws-ops-agent-dev \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:ap-southeast-1:123456789012:<API_ID>/*/*" \
  --region ap-southeast-1
```

## Power Automate 配置

### HTTP 動作設定

```json
{
  "type": "Http",
  "inputs": {
    "uri": "https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json",
      "X-Api-Key": "<YOUR_API_KEY>"
    },
    "body": {
      "query": "@{triggerBody()?['body']?['content']}",
      "session_id": "@{triggerBody()?['from']?['user']?['id']}"
    }
  }
}
```

### API Key

```
YOUR_API_KEY_HERE
```

## 測試

### 使用 curl

```bash
curl -X POST "https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY_HERE" \
  -d '{"query": "hello", "session_id": "test123"}'
```

### 使用 Postman

- Method: POST
- URL: https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod
- Headers:
  - Content-Type: application/json
  - x-api-key: <API_KEY>
- Body (raw JSON):
  ```json
  {
    "query": "hello",
    "session_id": "test123"
  }
  ```

## 管理命令

```bash
# 查看 API 資訊
aws apigatewayv2 get-api --api-id your-api-id --region ap-southeast-1

# 查看 Routes
aws apigatewayv2 get-routes --api-id your-api-id --region ap-southeast-1

# 查看 Integrations
aws apigatewayv2 get-integrations --api-id your-api-id --region ap-southeast-1

# 查看 Stages
aws apigatewayv2 get-stages --api-id your-api-id --region ap-southeast-1

# 刪除 API (如需重建)
aws apigatewayv2 delete-api --api-id your-api-id --region ap-southeast-1
```

## 架構圖

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Microsoft      │     │  API Gateway    │     │  Lambda         │
│  Teams          │     │  (HTTP API)     │     │  aws-ops-agent  │
│                 │     │                 │     │  -dev           │
│  User sends     │────▶│  POST /         │────▶│                 │
│  message        │     │  Validates      │     │  Processes      │
│                 │◀────│  request        │◀────│  query          │
│  Receives       │     │                 │     │                 │
│  response       │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │           Power Automate Flow                 │
        └───────────────────────────────────────────────┘
```

## 故障排除

### 403 Forbidden
- 檢查 Lambda 權限是否已授予 API Gateway
- 檢查 API Key 是否正確

### 500 Internal Server Error
- 檢查 Lambda CloudWatch Logs
- 確認 Lambda 環境變數設定正確

### Timeout
- API Gateway 預設 timeout 30 秒
- Lambda timeout 90 秒
- 如需更長時間，考慮使用異步調用

---

**Last Updated**: 2026-02-12
**API Gateway ID**: your-api-id
**Lambda Function**: aws-ops-agent-dev
