# AWSBot 使用指南

在 Microsoft Teams 中使用 AWS Operations AI Assistant 的完整指南。

## 🤖 什麼是 AWSBot？

AWSBot 是一個 AI 助手，可以幫你：
- 🔍 查詢 AWS 資源資訊
- 📊 檢查基礎設施狀態
- 🔎 調查 IP 和網路問題
- 📝 查詢日誌和追蹤請求流程

## 🚀 如何使用

### 基本語法

在 Teams Channel 中，使用 `@AWSBot` 提及 bot，然後輸入你的問題：

```
@AWSBot <你的問題>
```

### 回應流程

1. **立即回應**（< 5 秒）
   ```
   🔄 正在處理您的查詢...
   查詢: <你的問題>
   請稍候，結果將在處理完成後顯示。
   ```

2. **最終結果**（20-60 秒後）
   ```
   🤖 AWSBot 查詢結果
   <查詢結果>
   ⏱️ 執行時間: XXXXXms
   ```

## 📖 查詢範例

### 1. DNS 查詢

查詢服務的 DNS 記錄和相關資源。

**範例**:
```
@AWSBot 查詢 myapp 的 DNS
@AWSBot 找出 gitlab 的 FQDN
@AWSBot myapp-dev 的 DNS 是什麼
```

**回應範例**:
```
🤖 AWSBot 查詢結果

📍 DNS Information:
   FQDN: myapp-dev.internal.example.com
   Type: CNAME
   Value: alb-app-dev.internal.example.com

⚖️ Load Balancer:
   Name: alb-app-dev
   Type: Application Load Balancer
   DNS: alb-app-dev-123456789.ap-southeast-1.elb.amazonaws.com

🎯 Target Health:
   Healthy: 2
   Unhealthy: 0
   Total: 2

⏱️ 執行時間: 45000ms
```

### 2. ALB 狀態檢查

檢查 Application Load Balancer 的健康狀態。

**範例**:
```
@AWSBot 檢查 alb-app 的健康狀態
@AWSBot ALB alb-app-dev 的 targets 狀態
@AWSBot 查詢 ALB 健康檢查
```

**回應範例**:
```
🤖 AWSBot 查詢結果

⚖️ Load Balancer: alb-app-dev

🎯 Target Groups:
   ┌─────────────────────────────────────────────┐
   │ tg-myapp-dev                                  │
   │ • Healthy: 2/2                              │
   │ • Protocol: HTTP:8080                       │
   │ • Health Check: /health                     │
   └─────────────────────────────────────────────┘

📊 Overall Status: ✅ All targets healthy

⏱️ 執行時間: 32000ms
```

### 3. IP 調查

調查 IP 地址的來源和相關資源。

**範例**:
```
@AWSBot 調查 IP 10.0.1.100
@AWSBot 這個 IP 是什麼: 172.16.0.50
@AWSBot 查詢 IP 10.20.30.40 的資訊
```

**回應範例**:
```
🤖 AWSBot 查詢結果

🔍 IP Investigation: 10.0.1.100

📍 Location:
   VPC: vpc-12345678 (core-network-vpc)
   Subnet: subnet-abcdef12 (private-subnet-1a)
   AZ: ap-southeast-1a

🖥️ Associated Resource:
   Type: EC2 Instance
   ID: i-0123456789abcdef0
   Name: myapp-worker-01
   State: running

🔒 Security Groups:
   • sg-11111111: web-server-sg
   • sg-22222222: internal-access-sg

⏱️ 執行時間: 28000ms
```

### 4. FQDN 追蹤

追蹤完整的請求流程（F5 → Route53 → CloudFront → ALB）。

**範例**:
```
@AWSBot 追蹤 myapp-dev.example.com 的請求流程
@AWSBot trace gitlab.example.com
@AWSBot 查詢 app.example.com 的完整路徑
```

**回應範例**:
```
🤖 AWSBot 查詢結果

🔄 Request Flow Trace: myapp-dev.example.com

1️⃣ F5 WAF
   Virtual Server: vs-external-443
   Pool: pool-myapp-dev
   Status: ✅ Available

2️⃣ Route53
   Hosted Zone: example.com
   Record: myapp-dev.example.com
   Type: CNAME → internal.example.com

3️⃣ Internal DNS
   Record: myapp-dev.internal.example.com
   Type: CNAME → alb-app-dev.internal.example.com

4️⃣ Application Load Balancer
   Name: alb-app-dev
   Listener: HTTPS:443
   Target Group: tg-myapp-dev
   Targets: 2/2 healthy

5️⃣ Target Instances
   • i-0123456789abcdef0 (10.0.1.100) - healthy
   • i-0fedcba9876543210 (10.0.1.101) - healthy

✅ Complete path is healthy

⏱️ 執行時間: 58000ms
```

### 5. 日誌查詢

查詢 VPC Flow Logs 或 CloudFront 日誌。

**範例**:
```
@AWSBot 查詢 VPC Flow Logs 過去 1 小時
@AWSBot 檢查 CloudFront 日誌 過去 30 分鐘
@AWSBot 查詢 IP 10.0.1.100 的流量日誌
```

**回應範例**:
```
🤖 AWSBot 查詢結果

📝 VPC Flow Logs (過去 1 小時)

🔝 Top Source IPs:
   1. 10.0.1.100 - 1,234 connections
   2. 10.0.1.101 - 987 connections
   3. 10.0.2.50 - 456 connections

🎯 Top Destinations:
   1. 10.0.3.100:443 - 2,345 requests
   2. 10.0.3.101:80 - 1,234 requests

⚠️ Rejected Connections:
   • 192.168.1.100 → 10.0.1.100:22 (5 attempts)
   • 172.16.0.50 → 10.0.2.100:3389 (3 attempts)

⏱️ 執行時間: 42000ms
```

## 💡 使用技巧

### 1. 自然語言查詢

AWSBot 支援自然語言，你可以用各種方式問同一個問題：

```
@AWSBot 查詢 myapp 的 DNS
@AWSBot myapp 的 DNS 是什麼
@AWSBot 幫我找 myapp 的 DNS 記錄
@AWSBot 我想知道 myapp 的 DNS
```

### 2. 使用服務名稱

可以直接使用服務名稱，不需要完整的 FQDN：

```
@AWSBot 查詢 myapp          ✅
@AWSBot 查詢 gitlab       ✅
@AWSBot 查詢 jenkins      ✅
```

### 3. 組合查詢

可以在一個查詢中問多個問題：

```
@AWSBot 查詢 myapp 的 DNS 和健康狀態
@AWSBot 檢查 gitlab 的 ALB 和 targets
```

### 4. 時間範圍

查詢日誌時可以指定時間範圍：

```
@AWSBot 查詢 VPC Flow Logs 過去 1 小時
@AWSBot 查詢 CloudFront 日誌 過去 30 分鐘
@AWSBot 查詢日誌 過去 24 小時
```

## ⚠️ 限制和注意事項

### 回應時間
- **立即回應**: < 5 秒
- **最終結果**: 20-60 秒（取決於查詢複雜度）
- 如果超過 60 秒沒有回應，請檢查 Lambda 日誌或聯繫管理員

### 查詢限制
- 一次只能查詢一個主要資源
- 日誌查詢最多返回 100 筆記錄
- 時間範圍建議不超過 24 小時

### 權限
- Bot 使用 cross-account role 存取 AWS 資源
- 只能查詢已配置的 AWS 帳號
- 某些敏感資源可能無法查詢

## 🐛 常見問題

### Q: Bot 沒有回應怎麼辦？

**A**: 檢查以下項目：
1. 確認有正確 @ 提及 bot：`@AWSBot`
2. 等待至少 5 秒（立即回應）
3. 如果沒有任何回應，聯繫管理員檢查 Lambda 狀態

### Q: 收到 "處理中..." 但沒有最終結果？

**A**: 可能的原因：
1. Lambda 執行時間過長（> 5 分鐘）
2. Incoming Webhook 配置錯誤
3. 查詢過於複雜或資源不存在

請聯繫管理員查看 CloudWatch 日誌。

### Q: 結果不正確或不完整？

**A**: 
1. 確認查詢的資源名稱正確
2. 檢查是否有權限存取該資源
3. 嘗試更具體的查詢
4. 如果問題持續，請提供查詢內容給管理員

### Q: 可以在私訊中使用 Bot 嗎？

**A**: 不行，Outgoing Webhook 只支援 Channel 中的訊息。必須在 Channel 中 @ 提及 bot。

### Q: 可以同時發送多個查詢嗎？

**A**: 可以，但每個查詢都需要單獨 @ 提及 bot。Bot 會並行處理多個查詢。

### Q: 查詢會被記錄嗎？

**A**: 是的，所有查詢都會記錄在 CloudWatch Logs 中，用於監控和故障排除。請不要在查詢中包含敏感資訊。

## 📊 查詢類型總覽

| 查詢類型 | 關鍵字 | 執行時間 | 範例 |
|---------|--------|---------|------|
| DNS 查詢 | DNS, FQDN, 域名 | 20-30s | `@AWSBot 查詢 myapp 的 DNS` |
| ALB 狀態 | ALB, 健康, targets | 25-35s | `@AWSBot 檢查 ALB 健康狀態` |
| IP 調查 | IP, 調查, 查詢 | 20-30s | `@AWSBot 調查 IP 10.0.1.100` |
| FQDN 追蹤 | 追蹤, trace, 流程 | 40-60s | `@AWSBot 追蹤 myapp.example.com` |
| 日誌查詢 | 日誌, logs, VPC | 30-50s | `@AWSBot 查詢 VPC Flow Logs` |

## 🎯 最佳實踐

### 1. 明確的查詢

❌ 不好的查詢：
```
@AWSBot 檢查
@AWSBot 狀態
@AWSBot 查詢
```

✅ 好的查詢：
```
@AWSBot 查詢 myapp 的 DNS
@AWSBot 檢查 alb-app 的健康狀態
@AWSBot 調查 IP 10.0.1.100
```

### 2. 使用完整的資源名稱

❌ 不好：
```
@AWSBot 查詢 alb
@AWSBot 檢查 myapp
```

✅ 好：
```
@AWSBot 查詢 alb-app-dev
@AWSBot 檢查 myapp-dev
```

### 3. 指定時間範圍（日誌查詢）

❌ 不好：
```
@AWSBot 查詢日誌
```

✅ 好：
```
@AWSBot 查詢 VPC Flow Logs 過去 1 小時
```

## 📞 需要幫助？

如果遇到問題或需要協助：

1. **查看文件**:
   - 完整設定指南: `TEAMS_WEBHOOK_SETUP.md`
   - 快速開始: `TEAMS_INTEGRATION_QUICKSTART.md`

2. **聯繫管理員**:
   - 提供查詢內容
   - 提供錯誤訊息（如果有）
   - 提供查詢時間

3. **查看日誌**（管理員）:
   ```bash
   aws logs tail /aws/lambda/aws-ops-agent-dev --follow
   ```

## 🎉 開始使用

現在你已經了解如何使用 AWSBot 了！

試試看：
```
@AWSBot 查詢 myapp 的 DNS
```

祝你使用愉快！🚀

---

**版本**: 1.0  
**最後更新**: 2024-01  
**維護者**: AWS Ops Team
