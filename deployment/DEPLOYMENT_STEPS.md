# 🚀 AWS Operations Agent 部署步驟

## ✅ 答案：不需要手動創建 S3 Bucket！

部署腳本會**自動**為您創建所有需要的 S3 buckets。

---

## 📝 完整部署流程

### 前置條件

1. ✅ AWS CLI 已配置並有適當權限
2. ✅ F5 API Token 已獲取並測試通過
3. ✅ Python 3.11+ 已安裝

### 一鍵部署

```bash
# 1. 進入 deployment 目錄
cd deployment

# 2. 設置 F5 API Token
export F5_API_TOKEN="your-f5-api-token"

# 3. 運行部署腳本（會自動處理一切）
./setup_deployment.sh
```

就這麼簡單！🎉

---

## 🔧 腳本會自動完成的事情

### 1. 檢查前置條件
- ✅ 檢查 AWS CLI 是否安裝
- ✅ 檢查 AWS 憑證是否有效
- ✅ 檢查必需的權限

### 2. 驗證參數
- ✅ 驗證 Core Network Account ID
- ✅ 驗證 F5 API 配置
- ✅ 驗證其他必需參數

### 3. 構建部署包
- ✅ 運行 `build_package.sh`
- ✅ 創建 Lambda 函數包
- ✅ 創建 Lambda 層包

### 4. 創建 S3 Buckets（自動）
- ✅ **自動檢查** deployment bucket 是否存在
- ✅ **自動創建** deployment bucket（如果不存在）
- ✅ **自動啟用** bucket 版本控制
- ✅ **自動上傳** Lambda 部署包

### 5. 部署 CloudFormation 堆疊
- ✅ 創建所有 AWS 資源（Lambda, API Gateway, IAM, Secrets Manager 等）
- ✅ 等待部署完成
- ✅ 處理錯誤和回滾

### 6. 顯示部署結果
- ✅ API Gateway URL
- ✅ API Key（如果啟用）
- ✅ Lambda Function ARN
- ✅ 測試命令

---

## 📋 會創建的 S3 Buckets

腳本會自動創建以下 S3 buckets：

### 1. Deployment Bucket
- **名稱**: `aws-ops-agent-deployment-{account-id}-{region}`
- **用途**: 存儲 Lambda 部署包
- **內容**:
  - `lambda-layer.zip` (依賴層)
  - `aws-ops-agent-function.zip` (函數代碼)
- **特性**:
  - 版本控制已啟用
  - 自動創建（如果不存在）

### 2. Athena Results Bucket
- **名稱**: `aws-ops-agent-athena-results-{account-id}-{region}`
- **用途**: 存儲 Athena 查詢結果
- **特性**:
  - 由 CloudFormation 創建
  - 7天後自動刪除舊結果
  - 加密存儲

---

## 🎯 快速開始命令

### 完整的一鍵部署

```bash
# 設置環境變數
export F5_API_TOKEN="YOUR_F5_API_TOKEN_HERE"

# 運行部署（會自動創建 S3 buckets）
cd deployment
./setup_deployment.sh
```

### 如果您想手動控制每一步

```bash
# 1. 檢查 AWS 訪問
./check_aws_access.sh

# 2. 測試 F5 API
export F5_API_TOKEN="your-token"
./test_f5_connection.sh

# 3. 運行部署
./setup_deployment.sh
```

---

## ❓ 常見問題

### Q: 如果 S3 bucket 已經存在會怎樣？
**A**: 腳本會檢測到並跳過創建步驟，直接使用現有的 bucket。

### Q: 如果 S3 bucket 創建失敗會怎樣？
**A**: 腳本會顯示錯誤並停止部署。可能的原因：
- Bucket 名稱已被其他帳戶使用
- 沒有 S3 創建權限
- 區域配置錯誤

### Q: 我可以使用自己的 S3 bucket 嗎？
**A**: 可以！在運行腳本前設置環境變數：
```bash
export DEPLOYMENT_BUCKET="my-custom-bucket-name"
export ATHENA_OUTPUT_BUCKET="my-athena-bucket-name"
./setup_deployment.sh
```

### Q: 部署失敗後如何清理？
**A**: 運行清理命令：
```bash
# 刪除 CloudFormation 堆疊
aws cloudformation delete-stack --stack-name aws-ops-agent-complete

# 清理 S3 buckets
aws s3 rm s3://aws-ops-agent-deployment-{account}-{region} --recursive
aws s3 rb s3://aws-ops-agent-deployment-{account}-{region}
```

### Q: 部署需要多長時間？
**A**: 
- 構建包: 2-3 分鐘
- 上傳到 S3: 1-2 分鐘
- CloudFormation 部署: 5-10 分鐘
- **總計**: 約 10-15 分鐘

---

## 🔍 部署過程中的輸出

您會看到類似這樣的輸出：

```
========================================
  AWS Operations Agent - Complete Infrastructure Deployment
========================================

[INFO] Checking prerequisites...
✅ All prerequisites satisfied

[INFO] Validating parameters...
✅ All parameters validated

[STEP] Deployment Configuration
  Deployment Method: cloudformation
  Stack/Project Name: aws-ops-agent-complete
  Environment: prod
  Core Network Account: 234567890123
  ...

Do you want to proceed with the deployment? (y/N): y

[STEP] Building deployment packages...
✅ Build completed successfully

[INFO] Checking S3 buckets...
[INFO] Creating deployment bucket: aws-ops-agent-deployment-234567890123-us-east-1
✅ Deployment bucket created successfully

[INFO] Uploading packages to S3...
✅ Packages uploaded successfully

[STEP] Deploying infrastructure using CloudFormation...
[INFO] Creating new stack aws-ops-agent-complete...
[INFO] CloudFormation deployment initiated
[INFO] Waiting for stack deployment to complete...
✅ Stack deployment completed successfully

========================================
  Deployment Complete!
========================================

🚀 AWS Operations Agent deployed successfully!

📋 Deployment Summary:
  Environment: prod
  Lambda Function: arn:aws:lambda:us-east-1:234567890123:function:aws-ops-agent-prod
  API Gateway URL: https://abc123.execute-api.us-east-1.amazonaws.com/prod/query
  F5 Secret: arn:aws:secretsmanager:us-east-1:234567890123:secret:f5-api-credentials-xyz
  API Key: abc123xyz456

🧪 Test the API:
  curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/query \
    -H 'Content-Type: application/json' \
    -H 'x-api-key: abc123xyz456' \
    -d '{"query": "test"}'

📚 Next Steps:
  1. Test the API endpoint with sample queries
  2. Set up cross-account trust relationships
  3. Configure monitoring and alarms
  4. Review CloudWatch logs for any issues
```

---

## 🎉 總結

**您不需要手動創建任何 S3 bucket！**

只需運行：
```bash
export F5_API_TOKEN="your-token"
cd deployment
./setup_deployment.sh
```

腳本會自動處理一切，包括：
- ✅ 創建 S3 buckets
- ✅ 構建和上傳 Lambda 包
- ✅ 部署所有 AWS 資源
- ✅ 配置權限和安全設置
- ✅ 顯示測試命令

就這麼簡單！🚀
