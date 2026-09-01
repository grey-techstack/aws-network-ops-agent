# AWS Operations Agent 快速部署指南

## 前置條件

- AWS CLI 已配置並有適當權限
- Python 3.11+
- bash shell
- curl (用於測試)

## 快速部署步驟

### 1. 配置環境變數

編輯 `deploy-config.sh` 文件，填入您的配置：

```bash
cd deployment
nano deploy-config.sh  # 或使用您喜歡的編輯器
```

**必需修改的配置：**
- `F5_API_URL`: 您的 F5 Distributed Cloud API URL
- `F5_API_TOKEN`: 您的 F5 API Token
- `WORKLOAD_ACCOUNT_IDS`: 如果有其他工作負載帳戶，添加到這裡

**已配置的值：**
- `CORE_NETWORK_ACCOUNT_ID`: 234567890123 ✅

### 2. 測試 F5 API 連接

在部署之前，先測試 F5 API 是否可以正常連接：

```bash
# 加載配置
source deploy-config.sh

# 給腳本執行權限
chmod +x test_f5_api.sh

# 測試 F5 API
./test_f5_api.sh

# 如果要測試特定 FQDN
./test_f5_api.sh --fqdn demo.example.com
```

### 3. 執行自動化部署

```bash
# 確保在 deployment 目錄
cd deployment

# 加載配置
source deploy-config.sh

# 給部署腳本執行權限
chmod +x deploy_complete_infrastructure.sh
chmod +x build_package.sh

# 執行部署
./deploy_complete_infrastructure.sh
```

部署腳本會自動：
1. ✅ 檢查前置條件
2. ✅ 驗證參數
3. ✅ 建構 Lambda 部署包
4. ✅ 上傳到 S3
5. ✅ 部署 CloudFormation 堆疊
6. ✅ 顯示部署結果和測試命令

### 4. 測試部署

部署完成後，腳本會顯示 API Gateway URL 和測試命令。

```bash
# 測試 API（腳本會提供完整命令）
curl -X POST https://YOUR-API-ID.execute-api.REGION.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR-API-KEY" \
  -d '{"query": "trace demo.example.com"}'
```

## 常見問題

### Q: F5 API 測試失敗怎麼辦？

**A:** 檢查以下項目：
1. F5_API_URL 格式是否正確（應該是 `https://tenant.console.ves.volterra.io/api`）
2. F5_API_TOKEN 是否有效且未過期
3. API Token 是否有足夠的權限訪問 Load Balancer 配置
4. 網絡連接是否正常

### Q: 部署失敗怎麼辦？

**A:** 查看 CloudFormation 事件：
```bash
aws cloudformation describe-stack-events --stack-name aws-ops-agent-complete
```

### Q: 如何更新已部署的堆疊？

**A:** 重新運行部署腳本，它會自動檢測並更新現有堆疊：
```bash
./deploy_complete_infrastructure.sh
```

### Q: 如何刪除部署？

**A:** 刪除 CloudFormation 堆疊：
```bash
aws cloudformation delete-stack --stack-name aws-ops-agent-complete

# 等待刪除完成
aws cloudformation wait stack-delete-complete --stack-name aws-ops-agent-complete
```

## 手動配置步驟（如果自動化腳本失敗）

### 1. 建構部署包

```bash
cd deployment
./build_package.sh
```

### 2. 創建 S3 存儲桶

```bash
AWS_REGION=$(aws configure get region)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

DEPLOYMENT_BUCKET="aws-ops-agent-deployment-${AWS_ACCOUNT_ID}-${AWS_REGION}"
ATHENA_BUCKET="aws-ops-agent-athena-results-${AWS_ACCOUNT_ID}-${AWS_REGION}"

aws s3 mb "s3://$DEPLOYMENT_BUCKET"
aws s3 mb "s3://$ATHENA_BUCKET"
```

### 3. 上傳部署包

```bash
aws s3 cp lambda-layer.zip "s3://$DEPLOYMENT_BUCKET/lambda-layer.zip"
aws s3 cp aws-ops-agent-function.zip "s3://$DEPLOYMENT_BUCKET/aws-ops-agent-function.zip"
```

### 4. 部署 CloudFormation

```bash
source deploy-config.sh

aws cloudformation create-stack \
  --stack-name aws-ops-agent-complete \
  --template-body file://aws-ops-agent-complete.yaml \
  --parameters \
    ParameterKey=CoreNetworkAccountId,ParameterValue=$CORE_NETWORK_ACCOUNT_ID \
    ParameterKey=WorkloadAccountIds,ParameterValue=$WORKLOAD_ACCOUNT_IDS \
    ParameterKey=F5ApiUrl,ParameterValue=$F5_API_URL \
    ParameterKey=F5ApiToken,ParameterValue=$F5_API_TOKEN \
    ParameterKey=AthenaOutputBucket,ParameterValue=$ATHENA_BUCKET \
    ParameterKey=EnableApiKey,ParameterValue=$ENABLE_API_KEY \
  --capabilities CAPABILITY_NAMED_IAM
```

## 下一步

部署成功後：

1. ✅ 測試 API 端點
2. ✅ 配置跨帳戶信任關係（如果需要）
3. ✅ 設置 CloudWatch 監控和告警
4. ✅ 查看 CloudWatch 日誌確認運行正常

## 支持

如有問題，請查看：
- CloudWatch 日誌: `/aws/lambda/aws-ops-agent-prod`
- CloudFormation 事件
- 部署文檔: `infrastructure-as-code-guide.md`
