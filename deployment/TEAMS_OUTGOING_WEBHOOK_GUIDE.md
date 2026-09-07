# 如何在 Teams 中建立 Outgoing Webhook

這份指南將一步步教你如何在 Microsoft Teams 中建立 Outgoing Webhook。

## 📋 前置需求

- ✅ 你必須是 Team 的**擁有者**或有權限管理 Apps
- ✅ 已經有 API Gateway URL（從 `deploy_teams_webhook.sh` 取得）
- ✅ 已選擇要使用的 Teams Channel

## 🚀 建立步驟

### Step 1: 打開 Teams Apps

有兩種方式：

#### 方式 A: 從 Teams 左側欄（推薦）

1. 打開 Microsoft Teams
2. 點擊左側欄最下方的 **"Apps"** 圖示（或 **"應用程式"**）

```
┌─────────────────┐
│  Teams          │
│  📅 Calendar    │
│  📞 Calls       │
│  📁 Files       │
│  ...            │
│  🔲 Apps  ← 點這裡
└─────────────────┘
```

#### 方式 B: 從 Channel

1. 進入你要使用的 Channel
2. 點擊 Channel 名稱旁的 **"+"** 按鈕
3. 選擇 **"More apps"** 或 **"更多應用程式"**

### Step 2: 搜尋 Outgoing Webhook

1. 在搜尋框中輸入：**"Outgoing Webhook"**
2. 找到 **"Outgoing Webhook"** app（圖示是一個箭頭向外的圖標）
3. 點擊它

```
┌────────────────────────────────────┐
│  🔍 Search apps                    │
│  Outgoing Webhook                  │
└────────────────────────────────────┘

搜尋結果：
┌────────────────────────────────────┐
│  📤 Outgoing Webhook               │
│  Microsoft Corporation             │
│  Send messages to web services     │
└────────────────────────────────────┘
```

### Step 3: 加入到 Team

1. 點擊 **"Add to a team"** 或 **"新增至小組"**
2. 在下拉選單中選擇你的 **Team**
3. 選擇要使用的 **Channel**
4. 點擊 **"Set up a bot"** 或 **"設定 Bot"**

```
┌────────────────────────────────────┐
│  Add Outgoing Webhook to a team   │
│                                    │
│  Select a team:                    │
│  ▼ [Your Team Name]                │
│                                    │
│  Select a channel:                 │
│  ▼ [Your Channel Name]             │
│                                    │
│  [Set up a bot]                    │
└────────────────────────────────────┘
```

### Step 4: 配置 Outgoing Webhook

現在會出現配置畫面，填入以下資訊：

#### 4.1 Name（名稱）

```
Name: AWSBot
```

**說明**: 這是 bot 的名稱，用戶會用 `@AWSBot` 來呼叫它

**建議名稱**:
- `AWSBot`
- `AWSHelper`
- `CloudBot`
- `InfraBot`

#### 4.2 Callback URL（回調 URL）

```
Callback URL: https://xxxxxxxxxx.execute-api.ap-southeast-1.amazonaws.com/prod/query
```

**重要**: 這是從 `deploy_teams_webhook.sh` 輸出的 API Gateway URL

**如何取得**:
```bash
# 如果忘記了，可以執行：
aws cloudformation describe-stacks \
  --stack-name aws-ops-agent-api-gateway-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text
```

#### 4.3 Description（描述）- Optional

```
Description: AWS Operations AI Assistant - Query AWS infrastructure and resources
```

或中文：
```
Description: AWS 運維 AI 助手 - 查詢 AWS 基礎設施和資源
```

#### 4.4 Profile Picture（頭像）- Optional

你可以上傳一個 bot 圖示，建議：
- 尺寸：96x96 或更大
- 格式：PNG, JPG
- 內容：AWS logo 或機器人圖示

**配置畫面範例**:
```
┌────────────────────────────────────────────┐
│  Create an outgoing webhook               │
│                                            │
│  Name *                                    │
│  ┌──────────────────────────────────────┐ │
│  │ AWSBot                               │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  Callback URL *                            │
│  ┌──────────────────────────────────────┐ │
│  │ https://xxx.execute-api...           │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  Description                               │
│  ┌──────────────────────────────────────┐ │
│  │ AWS Operations AI Assistant          │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  Profile picture                           │
│  [Upload image]                            │
│                                            │
│  [Create]                                  │
└────────────────────────────────────────────┘
```

### Step 5: 建立並記錄 Security Token

1. 點擊 **"Create"** 或 **"建立"**
2. 會出現一個對話框顯示 **Security Token**
3. **重要**: 複製並儲存這個 token！

```
┌────────────────────────────────────────────┐
│  ✅ Outgoing webhook created               │
│                                            │
│  Security token:                           │
│  ┌──────────────────────────────────────┐ │
│  │ abc123xyz789...                      │ │
│  │ [Copy]                               │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  ⚠️  Save this token! You won't be able   │
│     to see it again.                       │
│                                            │
│  [Done]                                    │
└────────────────────────────────────────────┘
```

**儲存 Security Token**:
```bash
# 儲存到環境變數（建議）
export TEAMS_SECURITY_TOKEN='abc123xyz789...'

# 或記錄在安全的地方
echo "TEAMS_SECURITY_TOKEN=abc123xyz789..." >> .env.teams
```

### Step 6: 完成！

點擊 **"Done"** 或 **"完成"**

現在你的 Channel 中會出現一個通知：
```
┌────────────────────────────────────────────┐
│  🤖 AWSBot has been added to this channel │
└────────────────────────────────────────────┘
```

---

## 🧪 測試 Outgoing Webhook

### 測試 1: 簡單測試

在 Channel 中輸入：
```
@AWSBot test
```

**預期結果**（< 5 秒）:
```
🔄 正在處理您的查詢...

查詢: test

請稍候，結果將在處理完成後顯示。
```

然後（20-60 秒後）:
```
🤖 AWSBot 查詢結果

<查詢結果>

Time: 2026-01-27 17:00:00
```

### 測試 2: DNS 查詢

```
@AWSBot 查詢 myapp 的 DNS
```

**預期結果**:
```
🤖 AWSBot 查詢結果

✅ DNS 查詢成功

📍 域名: myapp-dev.internal.example.com
⚖️ ALB: alb-app-dev
🎯 Targets: 2/2 healthy

Time: 2026-01-27 17:00:00
```

---

## 🔍 如何找到已建立的 Outgoing Webhook

### 查看現有的 Webhooks

1. 進入 Channel
2. 點擊 Channel 名稱旁的 **"..."** (更多選項)
3. 選擇 **"Connectors"** 或 **"連接器"**
4. 找到 **"Configured"** 或 **"已配置"** 標籤
5. 你會看到 **"AWSBot"** 在列表中

### 管理 Webhook

在 Connectors 頁面，你可以：
- ✏️ **Edit** - 修改配置（但不能看到 Security Token）
- 🗑️ **Remove** - 刪除 webhook
- ℹ️ **View details** - 查看詳細資訊

---

## 🔧 進階配置（Optional）

### 加入 Security Token 驗證

為了安全，建議在 Lambda 中驗證 Teams 發送的 Security Token。

#### Step 1: 加入 Token 到 Lambda 環境變數

```bash
export TEAMS_SECURITY_TOKEN='your-security-token'

aws lambda update-function-configuration \
  --function-name aws-ops-agent-dev \
  --environment Variables="{
    TEAMS_INCOMING_WEBHOOK_URL=$TEAMS_INCOMING_WEBHOOK_URL,
    TEAMS_SECURITY_TOKEN=$TEAMS_SECURITY_TOKEN,
    ...其他環境變數...
  }"
```

#### Step 2: Lambda 會自動驗證

`src/teams_webhook_handler.py` 已經包含驗證邏輯（如果設定了 token）。

---

## 🐛 常見問題

### 問題 1: 找不到 "Outgoing Webhook" app

**原因**: 
- 你的組織可能禁用了這個 app
- 你沒有權限安裝 apps

**解決**:
1. 聯繫 Teams 管理員
2. 請求啟用 "Outgoing Webhook" app
3. 或請管理員幫你安裝

### 問題 2: "Add to a team" 按鈕是灰色的

**原因**: 你不是 Team 的擁有者

**解決**:
1. 請 Team 擁有者幫你安裝
2. 或請擁有者給你權限

### 問題 3: 建立後無法測試

**檢查**:
```bash
# 1. 確認 API Gateway URL 正確
curl -X POST "your-api-gateway-url" \
  -H "Content-Type: application/json" \
  -d '{"text":"test"}'

# 2. 查看 Lambda 日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow

# 3. 確認 Lambda handler 正確
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Handler'
```

### 問題 4: Bot 沒有回應

**可能原因**:
1. API Gateway URL 錯誤
2. Lambda 沒有部署
3. Lambda timeout
4. 環境變數未設定

**檢查步驟**:
```bash
# 1. 測試 API Gateway
curl -X POST "your-api-gateway-url" -d '{"text":"test"}'

# 2. 查看 Lambda 日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow

# 3. 執行測試腳本
cd deployment
./test_teams_webhook.sh
```

### 問題 5: 收到 "Unable to reach app"

**原因**: Teams 無法連接到你的 API Gateway

**檢查**:
1. API Gateway URL 是否正確
2. API Gateway 是否公開可訪問
3. Lambda 是否正常運行

```bash
# 測試 API Gateway
curl -v -X POST "your-api-gateway-url" \
  -H "Content-Type: application/json" \
  -d '{"type":"message","text":"test"}'
```

---

## 📊 Outgoing Webhook vs Incoming Webhook

| 特性 | Outgoing Webhook | Incoming Webhook |
|------|-----------------|------------------|
| **方向** | Teams → Lambda | Lambda → Teams |
| **用途** | 接收用戶訊息 | 發送結果到 Teams |
| **建立位置** | Apps | Connectors |
| **需要** | API Gateway URL | Webhook URL |
| **限制** | 5 秒 timeout | 無 timeout |
| **我們的方案** | 用於接收查詢 | 用於發送結果 |

**我們使用兩個 webhook**:
```
Outgoing Webhook (Teams → Lambda)
    ↓ 接收查詢
Lambda 處理
    ↓ 發送結果
Incoming Webhook (Lambda → Teams)
```

---

## 📝 配置總結

完成後，你應該有：

### Outgoing Webhook 配置
- ✅ Name: `AWSBot`
- ✅ Callback URL: `https://xxx.execute-api.ap-southeast-1.amazonaws.com/prod/query`
- ✅ Description: `AWS Operations AI Assistant`
- ✅ Security Token: `abc123xyz789...` (已儲存)

### Lambda 配置
- ✅ Handler: `src.teams_webhook_handler.lambda_handler`
- ✅ Environment Variables:
  - `TEAMS_INCOMING_WEBHOOK_URL` - Power Automate webhook
  - `TEAMS_SECURITY_TOKEN` - Outgoing webhook token (optional)
  - 其他現有變數

### 測試結果
- ✅ `@AWSBot test` - 收到回應
- ✅ `@AWSBot 查詢 myapp 的 DNS` - 收到查詢結果

---

## 🎯 下一步

1. **測試各種查詢**:
   - DNS 查詢
   - ALB 狀態
   - IP 調查
   - 日誌查詢

2. **分享給團隊**:
   - 分享 `deployment/TEAMS_USER_GUIDE.md`
   - 教團隊成員如何使用

3. **監控和優化**:
   - 查看 CloudWatch 日誌
   - 監控執行時間
   - 優化查詢效能

---

## 📚 相關文件

- `READY_TO_DEPLOY.md` - 部署指南
- `TEAMS_USER_GUIDE.md` - 使用者手冊
- `TEAMS_WEBHOOK_SETUP.md` - 完整設定指南
- `DEPLOY_SCRIPT_EXPLAINED.md` - 部署腳本說明

---

**恭喜！你已經成功建立 Teams Outgoing Webhook！** 🎉

現在可以在 Teams 中使用 `@AWSBot` 來查詢 AWS 資源了！
