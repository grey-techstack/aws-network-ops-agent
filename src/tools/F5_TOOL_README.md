# F5 Distributed Cloud WAF Tool

## 概述

F5 WAF Tool 提供了查詢 F5 Distributed Cloud 負載均衡器、Origin Pools 和虛擬主機的功能。

## 功能

### 1. 查詢 F5 Load Balancer (`query_f5_load_balancer`)

根據 FQDN 查詢 F5 負載均衡器配置。

**參數**:
- `fqdn`: 完整域名 (例如: `demo.example.com`)

**返回**:
```json
{
  "found": true,
  "fqdn": "demo.example.com",
  "load_balancer_name": "demo-lb",
  "namespace": "system",
  "domains": ["demo.example.com", "www.demo.example.com"],
  "origin_pools": [
    {
      "name": "demo-origin-pool",
      "namespace": "system",
      "type": "default_route"
    }
  ],
  "routes": [
    {
      "path": "/api",
      "origin_pools": [
        {
          "name": "api-origin-pool",
          "namespace": "system"
        }
      ]
    }
  ],
  "https_auto_cert": true,
  "port": 443
}
```

**使用範例**:
```python
# 在 Agent 中使用
query = "查詢 demo.example.com 的 F5 load balancer 配置"
```

### 2. 查詢 F5 Origin Pool (`query_f5_origin_pool`)

查詢 F5 Origin Pool 的詳細資訊，包括後端伺服器。

**參數**:
- `pool_name`: Origin Pool 名稱
- `namespace`: (可選) F5 namespace

**返回**:
```json
{
  "found": true,
  "pool_name": "demo-origin-pool",
  "namespace": "system",
  "origin_servers": [
    {
      "type": "public_name",
      "dns_name": "backend.example.com"
    },
    {
      "type": "public_ip",
      "ip": "203.0.113.10"
    }
  ],
  "port": 443,
  "health_check": {
    "path": "/health",
    "interval": 30,
    "timeout": 3,
    "unhealthy_threshold": 3,
    "healthy_threshold": 3
  },
  "loadbalancer_algorithm": "ROUND_ROBIN"
}
```

**使用範例**:
```python
# 在 Agent 中使用
query = "查詢 demo-origin-pool 的詳細資訊"
```

### 3. 列出所有 F5 Load Balancers (`list_f5_load_balancers`)

列出指定 namespace 中的所有 HTTP 負載均衡器。

**參數**:
- `namespace`: (可選) F5 namespace

**返回**:
```json
{
  "namespace": "system",
  "load_balancers": [
    {
      "name": "demo-lb",
      "namespace": "system",
      "domains": ["demo.example.com"],
      "origin_pool_count": 1,
      "route_count": 2
    },
    {
      "name": "api-lb",
      "namespace": "system",
      "domains": ["api.example.com"],
      "origin_pool_count": 2,
      "route_count": 5
    }
  ],
  "count": 2
}
```

**使用範例**:
```python
# 在 Agent 中使用
query = "列出所有 F5 load balancers"
```

## 設定

### 1. AWS Secrets Manager 配置

F5 API 憑證儲存在 AWS Secrets Manager 中。

**Secret 格式**:
```json
{
  "api_url": "https://example.console.example.io/api",
  "api_token": "your-api-token-here",
  "namespace": "system"
}
```

**環境變數**:
```bash
F5_SECRET_NAME=f5-distributed-cloud-api-credentials
```

### 2. 創建 Secret

```bash
aws secretsmanager create-secret \
  --name f5-distributed-cloud-api-credentials \
  --description "F5 Distributed Cloud API credentials" \
  --secret-string '{
    "api_url": "https://example.console.example.io/api",
    "api_token": "your-api-token",
    "namespace": "system"
  }'
```

### 3. 更新 Secret

```bash
aws secretsmanager update-secret \
  --secret-id f5-distributed-cloud-api-credentials \
  --secret-string '{
    "api_url": "https://example.console.example.io/api",
    "api_token": "new-api-token",
    "namespace": "system"
  }'
```

## API Token 權限

F5 API Token 需要以下**最小權限**:

- ✅ `ves-io-read-global` - 全局讀取權限
- ✅ 或特定 namespace 的讀取權限

**需要訪問的資源**:
- HTTP Load Balancers (讀取)
- Origin Pools (讀取)
- Namespaces (列表)

## 測試

### 1. 測試 F5 API 連接

```bash
cd deployment
./test_f5_api.sh
```

### 2. 測試 F5 工具整合

```bash
cd deployment
./test_f5_tool.sh
```

### 3. 手動測試

```bash
# Assume role
eval "$(./aws-assume-role.sh arn:aws:iam::123456789012:role/OrganizationAccountAccessRole MySession 3600)"

# Test query
aws lambda invoke \
  --function-name aws-ops-agent-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"query": "list all F5 load balancers"}' \
  response.json && cat response.json
```

## 使用範例

### 查詢域名的完整路徑

```
查詢 demo.example.com 的完整基礎架構路徑，包括 F5 load balancer 和 origin pools
```

這會：
1. 查詢 Route53 DNS 記錄
2. 查詢 F5 load balancer 配置
3. 查詢 F5 origin pools
4. 查詢 ALB/NLB (如果有)
5. 顯示完整的流量路徑

### 檢查 F5 後端健康狀態

```
檢查 demo-origin-pool 的健康檢查配置和後端伺服器
```

### 列出所有 F5 資源

```
列出所有 F5 load balancers 和它們的域名
```

## Origin Server 類型

F5 支援多種 origin server 類型：

### 1. Public Name
```json
{
  "type": "public_name",
  "dns_name": "backend.example.com"
}
```

### 2. Public IP
```json
{
  "type": "public_ip",
  "ip": "203.0.113.10"
}
```

### 3. Private Name
```json
{
  "type": "private_name",
  "dns_name": "internal-backend.local",
  "site_locator": {
    "site": "aws-site-1"
  }
}
```

### 4. Private IP
```json
{
  "type": "private_ip",
  "ip": "10.0.1.100",
  "site_locator": {
    "site": "aws-site-1"
  }
}
```

### 5. Kubernetes Service
```json
{
  "type": "k8s_service",
  "service_name": "my-service",
  "site_locator": {
    "site": "k8s-cluster-1"
  }
}
```

## 錯誤處理

### 常見錯誤

#### 1. Secret 不存在
```json
{
  "error": "F5 credentials secret not found: f5-distributed-cloud-api-credentials"
}
```

**解決方案**: 創建 Secret (參考上面的設定部分)

#### 2. API Token 無效
```json
{
  "error": "F5 API request failed: 401 Unauthorized"
}
```

**解決方案**: 
- 檢查 API Token 是否正確
- 檢查 Token 是否過期
- 更新 Secret 中的 Token

#### 3. 權限不足
```json
{
  "error": "F5 API request failed: 403 Forbidden"
}
```

**解決方案**: 
- 檢查 API Token 權限
- 確保有讀取權限

#### 4. Load Balancer 不存在
```json
{
  "found": false,
  "message": "No F5 load balancer found for FQDN: demo.example.com"
}
```

**說明**: 該域名沒有配置 F5 load balancer

## 日誌和監控

所有 F5 工具執行都會記錄到 CloudWatch Logs：

```bash
# 查看日誌
aws logs tail /aws/lambda/aws-ops-agent-dev --follow
```

**日誌包含**:
- 工具名稱
- 參數
- 執行時間
- 成功/失敗狀態
- 錯誤訊息 (如果有)

## 最佳實踐

1. **使用 Read-Only Token**: 只給予必要的讀取權限
2. **定期輪換 Token**: 設置 Token 過期時間並定期更新
3. **監控 API 使用**: 定期檢查 API 調用次數和錯誤率
4. **快取結果**: 工具自動快取結果 1 小時，減少 API 調用
5. **錯誤處理**: 工具會自動重試暫時性錯誤

## 故障排除

### 檢查 F5 Secret

```bash
aws secretsmanager get-secret-value \
  --secret-id f5-distributed-cloud-api-credentials \
  --query SecretString \
  --output text | jq '.'
```

### 測試 F5 API 連接

```bash
export F5_API_URL="https://example.console.example.io/api"
export F5_API_TOKEN="your-token"

curl -H "Authorization: APIToken $F5_API_TOKEN" \
     -H "Content-Type: application/json" \
     "$F5_API_URL/web/namespaces"
```

### 檢查 Lambda 環境變數

```bash
aws lambda get-function-configuration \
  --function-name aws-ops-agent-dev \
  --query 'Environment.Variables.F5_SECRET_NAME' \
  --output text
```

## 相關文件

- `deployment/F5_API_SETUP_GUIDE.md` - F5 API Token 設置指南
- `deployment/f5-secret-example.py` - F5 憑證管理範例
- `src/agent/error_handlers.py` - F5 錯誤處理
- `src/agent/formatters.py` - F5 結果格式化

## 支援

如果遇到問題：
1. 檢查 CloudWatch Logs
2. 驗證 F5 API Token
3. 測試 F5 API 連接
4. 查看錯誤訊息和故障排除指南
