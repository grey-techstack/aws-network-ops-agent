# F5 Distributed Cloud API Token 設置指南

## 您的 F5 Console URL
`https://example.console.example.io/`

## API Endpoint URL
基於您的 console URL，API endpoint 應該是：
```
https://example.console.example.io/api
```

## 如何獲取 API Token

### 方法 1：通過 F5 Console UI 創建 API Token

1. **登入 F5 Distributed Cloud Console**
   - 訪問: https://example.console.example.io/
   - 使用您的憑證登入

2. **導航到 API Credentials 頁面**
   - 點擊右上角的用戶圖標
   - 選擇 "Account Settings" 或 "Credentials"
   - 找到 "API Credentials" 或 "API Tokens" 選項

3. **創建新的 API Token**
   - 點擊 "Add Credentials" 或 "Create API Token"
   - 選擇類型: **API Token**
   - 設置名稱: 例如 "aws-ops-agent-readonly"
   - 設置過期時間（建議至少 90 天）
   - **重要**: 選擇權限為 **Read-Only** 或 **Viewer**

4. **保存 API Token**
   - 創建後，**立即複製並保存** API Token
   - ⚠️ Token 只會顯示一次，之後無法再次查看
   - 建議保存到安全的密碼管理器

### 方法 2：通過 API Credentials 頁面

1. 訪問: https://example.console.example.io/web/administration/personal-management
2. 點擊 "Credentials" 標籤
3. 點擊 "Add Credentials"
4. 選擇 "API Token"
5. 填寫信息並創建

### 方法 3：使用現有的 Service Account

如果您的組織已經有 Service Account：

1. 訪問: https://example.console.example.io/web/administration/service-credentials
2. 找到具有 read-only 權限的 Service Account
3. 獲取其 API Token

## API Token 權限要求

對於 AWS Operations Agent，需要以下**最小權限**：

### Read-Only 權限（推薦）
- ✅ `ves-io-read-global` - 全局讀取權限
- ✅ 或者特定的 namespace 讀取權限

### 具體需要訪問的資源
- HTTP Load Balancers (讀取)
- Origin Pools (讀取)
- VES Endpoints (讀取)
- Namespaces (列表)

## 測試 API Token

創建 Token 後，使用以下命令測試：

```bash
# 設置環境變數
export F5_API_URL="https://example.console.example.io/api"
export F5_API_TOKEN="your-api-token-here"

# 測試連接
curl -H "Authorization: APIToken $F5_API_TOKEN" \
     -H "Content-Type: application/json" \
     "$F5_API_URL/web/namespaces"
```

成功的響應應該返回 namespace 列表。

## 常見問題

### Q: 我找不到 API Credentials 選項
**A**: 檢查您的用戶權限。您可能需要：
- 管理員權限來創建 API Token
- 或者請管理員為您創建一個 read-only API Token

### Q: API Token 過期了怎麼辦？
**A**: 
1. 在 F5 Console 中刪除舊的 Token
2. 創建新的 Token
3. 更新 AWS Secrets Manager 中的值

### Q: 我應該使用哪個 namespace？
**A**: 
- 默認使用 `system` namespace
- 如果您的 Load Balancers 在其他 namespace，請使用相應的 namespace
- 可以通過 API 列出所有可用的 namespaces

## 安全最佳實踐

1. ✅ **使用 Read-Only Token**: 只給予必要的讀取權限
2. ✅ **設置過期時間**: 定期輪換 API Token
3. ✅ **安全存儲**: 使用 AWS Secrets Manager 存儲 Token
4. ✅ **監控使用**: 定期檢查 API Token 的使用情況
5. ✅ **限制範圍**: 如果可能，限制 Token 只能訪問特定 namespace

## 下一步

獲取 API Token 後：

1. 運行測試腳本驗證連接：
   ```bash
   cd deployment
   export F5_API_URL="https://example.console.example.io/api"
   export F5_API_TOKEN="your-token"
   ./test_f5_api.sh
   ```

2. 如果測試成功，繼續部署：
   ```bash
   ./setup_deployment.sh
   ```

## 需要幫助？

如果您在獲取 API Token 時遇到問題：
1. 聯繫您的 F5 管理員
2. 查看 F5 Distributed Cloud 文檔
3. 檢查您的用戶權限設置
