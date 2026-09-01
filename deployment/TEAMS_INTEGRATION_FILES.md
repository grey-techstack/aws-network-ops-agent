# Teams Integration - 文件清單

這份文件列出所有與 Teams 整合相關的文件和它們的用途。

## 📁 核心文件

### 1. `src/teams_webhook_handler.py`
**用途**: Lambda handler for Teams webhook integration  
**類型**: Python source code  
**說明**: 
- 處理 Teams Outgoing Webhook 請求
- 支援同步和異步模式
- 解析 Teams payload
- 發送結果到 Teams Incoming Webhook

**關鍵功能**:
- `parse_teams_webhook_event()` - 解析 Teams 請求
- `send_teams_message()` - 發送訊息到 Teams
- `process_query_and_send_to_teams()` - 處理查詢
- `lambda_handler()` - 主要 handler

---

## 📚 文件檔案

### 2. `deployment/TEAMS_INTEGRATION_QUICKSTART.md`
**用途**: 5 分鐘快速設定指南  
**適合**: 第一次設定的人  
**內容**:
- ✅ 快速設定步驟（3 個主要步驟）
- ✅ 測試方法
- ✅ 使用範例
- ✅ 故障排除
- ✅ 架構說明

**何時使用**: 想要快速開始使用 Teams 整合

---

### 3. `deployment/TEAMS_WEBHOOK_SETUP.md`
**用途**: 完整詳細的設定指南  
**適合**: 需要深入了解的人  
**內容**:
- 📖 架構概覽
- 📖 為什麼需要兩個 webhook
- 📖 詳細設定步驟
- 📖 進階配置
- 📖 監控和日誌
- 📖 故障排除

**何時使用**: 需要完整理解整個系統或進行進階配置

---

### 4. `deployment/TEAMS_SETUP_CHECKLIST.md`
**用途**: 設定檢查清單  
**適合**: 確保所有步驟都完成  
**內容**:
- ☑️ 前置準備檢查
- ☑️ 每個步驟的 checkbox
- ☑️ 驗證清單
- ☑️ 故障排除步驟
- ☑️ 完成記錄

**何時使用**: 設定過程中，確保不遺漏任何步驟

---

### 5. `deployment/TEAMS_USER_GUIDE.md`
**用途**: 終端使用者指南  
**適合**: 使用 Teams bot 的團隊成員  
**內容**:
- 👥 如何使用 bot
- 👥 查詢範例
- 👥 使用技巧
- 👥 常見問題
- 👥 最佳實踐

**何時使用**: 分享給團隊成員，教他們如何使用 bot

---

### 6. `deployment/teams-webhook-flow.txt`
**用途**: 架構流程圖（ASCII art）  
**適合**: 視覺化理解整個流程  
**內容**:
- 🎨 完整的請求流程圖
- 🎨 時間分解
- 🎨 關鍵優點
- 🎨 所需組件
- 🎨 安全考量

**何時使用**: 需要理解或解釋整個系統架構

---

## 🔧 腳本文件

### 7. `deployment/deploy_teams_webhook.sh`
**用途**: 一鍵部署腳本  
**類型**: Bash script  
**功能**:
- 🚀 打包 Lambda code
- 🚀 更新 Lambda function
- 🚀 設定環境變數
- 🚀 更新 handler
- 🚀 加入自調用權限
- 🚀 顯示 API Gateway URL

**使用方法**:
```bash
export TEAMS_INCOMING_WEBHOOK_URL='your-webhook-url'
./deploy_teams_webhook.sh
```

---

### 8. `deployment/test_teams_webhook.sh`
**用途**: 測試腳本  
**類型**: Bash script  
**測試項目**:
- ✅ Lambda function 存在
- ✅ Handler 配置
- ✅ 環境變數
- ✅ 自調用權限
- ✅ Lambda 功能
- ✅ API Gateway
- ✅ Incoming Webhook

**使用方法**:
```bash
./test_teams_webhook.sh
```

---

## ⚙️ 配置文件

### 9. `deployment/.env.teams.example`
**用途**: 環境變數範例  
**類型**: Environment file template  
**內容**:
- 🔧 TEAMS_INCOMING_WEBHOOK_URL
- 🔧 TEAMS_SECURITY_TOKEN
- 🔧 FUNCTION_NAME
- 🔧 AWS_REGION
- 🔧 其他 Lambda 環境變數

**使用方法**:
```bash
cp .env.teams.example .env.teams
# 編輯 .env.teams 填入實際值
source .env.teams
```

---

### 10. `deployment/TEAMS_INTEGRATION_FILES.md`
**用途**: 文件清單（本文件）  
**類型**: Documentation index  
**內容**: 所有 Teams 整合相關文件的說明

---

## 📊 文件使用流程

### 第一次設定

```
1. 閱讀 TEAMS_INTEGRATION_QUICKSTART.md
   ↓
2. 使用 TEAMS_SETUP_CHECKLIST.md 進行設定
   ↓
3. 執行 deploy_teams_webhook.sh
   ↓
4. 執行 test_teams_webhook.sh
   ↓
5. 分享 TEAMS_USER_GUIDE.md 給團隊
```

### 深入理解

```
1. 閱讀 TEAMS_WEBHOOK_SETUP.md
   ↓
2. 查看 teams-webhook-flow.txt
   ↓
3. 檢視 src/teams_webhook_handler.py
```

### 故障排除

```
1. 查看 TEAMS_SETUP_CHECKLIST.md 的故障排除部分
   ↓
2. 執行 test_teams_webhook.sh
   ↓
3. 參考 TEAMS_WEBHOOK_SETUP.md 的故障排除章節
```

### 使用者培訓

```
1. 分享 TEAMS_USER_GUIDE.md
   ↓
2. 示範幾個查詢範例
   ↓
3. 讓使用者參考常見問題部分
```

## 🎯 快速參考

### 我想要...

| 需求 | 使用文件 |
|------|---------|
| 快速開始設定 | `TEAMS_INTEGRATION_QUICKSTART.md` |
| 完整設定指南 | `TEAMS_WEBHOOK_SETUP.md` |
| 確保不遺漏步驟 | `TEAMS_SETUP_CHECKLIST.md` |
| 教團隊使用 bot | `TEAMS_USER_GUIDE.md` |
| 理解架構 | `teams-webhook-flow.txt` |
| 部署更新 | `deploy_teams_webhook.sh` |
| 測試功能 | `test_teams_webhook.sh` |
| 配置環境變數 | `.env.teams.example` |
| 查看程式碼 | `src/teams_webhook_handler.py` |

## 📝 文件維護

### 更新文件時

1. **程式碼變更**:
   - 更新 `src/teams_webhook_handler.py`
   - 更新 `TEAMS_WEBHOOK_SETUP.md` 的相關部分
   - 更新 `teams-webhook-flow.txt` 如果流程改變

2. **新增功能**:
   - 更新 `TEAMS_USER_GUIDE.md` 加入新的查詢範例
   - 更新 `TEAMS_INTEGRATION_QUICKSTART.md` 如果影響設定流程
   - 更新 `TEAMS_SETUP_CHECKLIST.md` 加入新的檢查項目

3. **修復 bug**:
   - 更新 `TEAMS_WEBHOOK_SETUP.md` 的故障排除部分
   - 更新 `TEAMS_SETUP_CHECKLIST.md` 的故障排除部分
   - 更新 `test_teams_webhook.sh` 加入新的測試

4. **配置變更**:
   - 更新 `.env.teams.example`
   - 更新 `deploy_teams_webhook.sh`
   - 更新所有文件中的環境變數說明

## 🔗 相關文件

### 其他部署文件

- `deployment/DEPLOYMENT_STEPS.md` - 完整部署指南
- `deployment/QUICK_START.md` - 快速開始
- `deployment/API_GATEWAY_SETUP.md` - API Gateway 設定
- `deployment/lambda-deployment-guide.md` - Lambda 部署指南

### 主要文件

- `README.md` - 專案主要 README
- `ENVIRONMENT_VARIABLES.md` - 環境變數說明
- `IMPLEMENTATION_SUMMARY.md` - 實作總結

## 📦 文件打包

### 給新團隊成員

打包以下文件：
```
TEAMS_INTEGRATION_QUICKSTART.md
TEAMS_USER_GUIDE.md
```

### 給系統管理員

打包以下文件：
```
TEAMS_WEBHOOK_SETUP.md
TEAMS_SETUP_CHECKLIST.md
teams-webhook-flow.txt
deploy_teams_webhook.sh
test_teams_webhook.sh
.env.teams.example
```

### 給開發人員

打包以下文件：
```
所有上述文件
src/teams_webhook_handler.py
```

## 🎓 學習路徑

### 初學者

1. `TEAMS_INTEGRATION_QUICKSTART.md` - 了解基本概念
2. `TEAMS_USER_GUIDE.md` - 學習如何使用
3. 實際操作 - 在 Teams 中測試

### 中級

1. `TEAMS_WEBHOOK_SETUP.md` - 深入理解設定
2. `teams-webhook-flow.txt` - 理解架構
3. `TEAMS_SETUP_CHECKLIST.md` - 完整設定流程

### 進階

1. `src/teams_webhook_handler.py` - 閱讀程式碼
2. `deploy_teams_webhook.sh` - 理解部署流程
3. `test_teams_webhook.sh` - 理解測試方法
4. 自訂和擴展功能

## 📞 支援

如果文件有任何問題或建議：

1. 檢查是否有更新版本
2. 查看相關的故障排除章節
3. 聯繫維護團隊

---

**文件版本**: 1.0  
**建立日期**: 2024-01  
**維護者**: AWS Ops Team  
**最後更新**: 2024-01
