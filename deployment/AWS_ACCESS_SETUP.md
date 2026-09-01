# AWS 訪問配置指南

## 部署 AWS Operations Agent 需要的 AWS 權限

要部署此應用程序，您需要具有以下 AWS 服務的權限：

### 必需的 AWS 服務權限

1. **Lambda** - 創建和管理 Lambda 函數
2. **IAM** - 創建和管理 IAM 角色和策略
3. **API Gateway** - 創建和配置 API Gateway
4. **S3** - 創建存儲桶並上傳部署包
5. **Secrets Manager** - 存儲 F5 API credentials
6. **CloudFormation** - 部署基礎設施堆疊
7. **CloudWatch Logs** - 查看日誌

## 配置 AWS 訪問的方法

### 方法 1：AWS SSO (推薦用於企業環境)

如果您的組織使用 AWS SSO：

```bash
# 1. 配置 AWS SSO
aws configure sso

# 按提示輸入：
# SSO start URL: https://your-org.awsapps.com/start
# SSO Region: us-east-1 (或您的區域)
# 選擇您的 AWS 帳戶和角色

# 2. 登入
aws sso login --profile your-profile-name

# 3. 設置為默認 profile
export AWS_PROFILE=your-profile-name

# 4. 驗證訪問
aws sts get-caller-identity
```

### 方法 2：AWS IAM 用戶 Access Keys

如果您有 IAM 用戶的 Access Key：

```bash
# 1. 配置 AWS CLI
aws configure

# 按提示輸入：
# AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
# AWS Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
# Default region name: us-east-1 (或您的區域)
# Default output format: json

# 2. 驗證訪問
aws sts get-caller-identity
```

### 方法 3：臨時憑證 (Session Token)

如果您使用 MFA 或臨時憑證：

```bash
# 1. 獲取臨時憑證
aws sts get-session-token --serial-number arn:aws:iam::ACCOUNT-ID:mfa/USER --token-code 123456

# 2. 設置環境變數
export AWS_ACCESS_KEY_ID=ASIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_SESSION_TOKEN=FwoGZXIvYXdzEBYaD...

# 3. 驗證訪問
aws sts get-caller-identity
```

## 檢查當前 AWS 訪問

運行以下命令檢查您的 AWS 配置：

```bash
# 檢查當前身份
aws sts get-caller-identity

# 應該返回類似：
# {
#     "UserId": "AIDAI...",
#     "Account": "234567890123",
#     "Arn": "arn:aws:iam::234567890123:user/your-username"
# }

# 檢查當前區域
aws configure get region

# 檢查當前 profile
echo $AWS_PROFILE
```

## 所需的 IAM 權限

您的 AWS 用戶/角色需要以下權限：

### 最小權限策略 (JSON)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:PublishLayerVersion",
        "lambda:GetFunction",
        "lambda:GetLayerVersion",
        "lambda:AddPermission",
        "lambda:RemovePermission"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:PassRole",
        "iam:CreatePolicy",
        "iam:GetPolicy",
        "iam:GetPolicyVersion"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "apigateway:*"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutBucketPolicy",
        "s3:PutBucketVersioning"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:GetTemplate"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
```

## 常見問題

### Q: 我沒有足夠的權限怎麼辦？

**A:** 聯繫您的 AWS 管理員，請求以下權限：
- Lambda 完整訪問
- IAM 角色創建和管理
- API Gateway 完整訪問
- S3 存儲桶創建和管理
- Secrets Manager 訪問
- CloudFormation 堆疊管理

### Q: 如何知道我有哪些權限？

**A:** 運行以下命令測試：

```bash
# 測試 Lambda 權限
aws lambda list-functions

# 測試 S3 權限
aws s3 ls

# 測試 IAM 權限
aws iam list-roles

# 測試 CloudFormation 權限
aws cloudformation list-stacks
```

### Q: 我使用的是 AWS SSO，如何配置？

**A:** 
1. 運行 `aws configure sso`
2. 輸入您組織的 SSO URL
3. 選擇帳戶 234567890123
4. 選擇具有管理員或 PowerUser 權限的角色
5. 運行 `aws sso login --profile your-profile`

### Q: 部署需要多長時間？

**A:** 
- 首次部署：約 10-15 分鐘
- 更新部署：約 5-10 分鐘

### Q: 部署會產生哪些費用？

**A:** 主要費用來源：
- Lambda 調用和執行時間
- API Gateway 請求
- S3 存儲
- CloudWatch Logs
- Athena 查詢

預計每月費用：$10-50（取決於使用量）

## 驗證 AWS 訪問的快速腳本

創建並運行此腳本來驗證您的 AWS 訪問：

```bash
#!/bin/bash
# check_aws_access.sh

echo "檢查 AWS 訪問..."
echo ""

# 檢查 AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI 未安裝"
    exit 1
fi
echo "✅ AWS CLI 已安裝"

# 檢查身份
if aws sts get-caller-identity &> /dev/null; then
    echo "✅ AWS 憑證有效"
    aws sts get-caller-identity
else
    echo "❌ AWS 憑證無效或未配置"
    exit 1
fi

echo ""
echo "檢查必需的權限..."

# 檢查 Lambda 權限
if aws lambda list-functions --max-items 1 &> /dev/null; then
    echo "✅ Lambda 權限"
else
    echo "❌ Lambda 權限不足"
fi

# 檢查 S3 權限
if aws s3 ls &> /dev/null; then
    echo "✅ S3 權限"
else
    echo "❌ S3 權限不足"
fi

# 檢查 IAM 權限
if aws iam list-roles --max-items 1 &> /dev/null; then
    echo "✅ IAM 權限"
else
    echo "❌ IAM 權限不足"
fi

# 檢查 CloudFormation 權限
if aws cloudformation list-stacks --max-items 1 &> /dev/null; then
    echo "✅ CloudFormation 權限"
else
    echo "❌ CloudFormation 權限不足"
fi

echo ""
echo "檢查完成！"
```

## 下一步

配置好 AWS 訪問後：

1. ✅ 驗證訪問：`aws sts get-caller-identity`
2. ✅ 設置 F5 Token：`export F5_API_TOKEN=your-token`
3. ✅ 運行部署：`./setup_deployment.sh`
