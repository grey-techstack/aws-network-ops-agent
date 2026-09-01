# 優化建置指南

## 🚀 使用優化的建置腳本

我們使用 `build_package_optimized.sh` 來建立 Lambda 套件，它比標準的 `build_package.sh` 更快、更小。

## 📊 優化版 vs 標準版

| 特性 | 標準版 | 優化版 |
|------|--------|--------|
| **建置時間** | 5-10 分鐘 | 1-3 分鐘（有快取時 < 30 秒） |
| **套件大小** | ~150MB | ~80MB |
| **依賴快取** | ❌ 每次重新下載 | ✅ 快取重複使用 |
| **增量建置** | ❌ 每次完整建置 | ✅ 只重建變更部分 |
| **測試套件** | ✅ 包含 | ❌ 排除（生產環境不需要） |

## 🔧 使用方式

### 方法 1: 使用部署腳本（推薦）

```bash
export TEAMS_INCOMING_WEBHOOK_URL='your-webhook-url'
cd deployment
./deploy_teams_webhook.sh
```

部署腳本會自動使用優化建置：
```bash
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

### 方法 2: 手動建置

```bash
cd deployment

# 使用快取（推薦）
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

# 或不使用快取
bash build_package_optimized.sh
```

## 💡 優化功能詳解

### 1. 依賴快取（Dependency Cache）

**問題**: 每次建置都重新下載所有 Python 套件（5-10 分鐘）

**解決**: 使用 pip 快取目錄

```bash
PIP_CACHE_DIR=build/.pip-cache
```

**效果**:
- 第一次建置：5-10 分鐘（下載所有套件）
- 後續建置：1-3 分鐘（從快取讀取）
- 如果依賴沒變：< 30 秒（完全跳過安裝）

**快取位置**:
```
deployment/
  build/
    .pip-cache/        ← pip 下載的套件快取
    .deps_hash         ← 依賴版本的 hash
    lambda_layer/      ← 已安裝的依賴
```

### 2. 增量建置（Incremental Build）

**智能檢測**:
```bash
# 計算 requirements-lambda.txt 的 hash
current_hash=$(sha256sum requirements-lambda.txt | awk '{print $1}')

# 與上次建置比較
if [ "$current_hash" = "$prev_hash" ]; then
    # 依賴沒變，重複使用現有的 lambda_layer
    REUSE_LAYER="true"
fi
```

**建置流程**:
```
檢查 requirements-lambda.txt
  ↓
計算 hash
  ↓
與上次比較
  ↓
┌─────────────┬─────────────┐
│ 依賴沒變    │ 依賴有變    │
├─────────────┼─────────────┤
│ 重複使用    │ 重新安裝    │
│ < 30 秒     │ 1-3 分鐘    │
└─────────────┴─────────────┘
  ↓
複製程式碼
  ↓
打包 zip
  ↓
完成
```

### 3. 生產依賴（Production Dependencies）

**標準版** (`requirements.txt`):
```
langchain==0.1.0          # 完整套件 ~100MB
pytest==7.4.3             # 測試工具
hypothesis==6.92.1        # 測試工具
moto==4.2.9               # AWS mock
...
```

**優化版** (`requirements-lambda.txt`):
```
langchain-core==0.1.10    # 核心功能 ~20MB
langchain-aws==0.1.0      # AWS 整合
boto3==1.34.0             # AWS SDK
dnspython==2.4.2          # DNS 查詢
requests==2.31.0          # HTTP 請求
# 不包含測試工具
```

**大小比較**:
- 標準版：~150MB
- 優化版：~80MB
- 節省：~47%

### 4. 檔案清理（File Cleanup）

自動移除不需要的檔案：

```bash
# 移除測試檔案
find "$LAYER_DIR/python" -type d -name "tests" -exec rm -rf {} +
find "$LAYER_DIR/python" -type d -name "test" -exec rm -rf {} +

# 移除 __pycache__ 和 .pyc
find "$LAYER_DIR/python" -type d -name "__pycache__" -exec rm -rf {} +
find "$LAYER_DIR/python" -type f -name "*.pyc" -delete

# 移除文件檔案
find "$LAYER_DIR/python" -type f -name "*.md" -delete
find "$LAYER_DIR/python" -type f -name "*.rst" -delete
find "$LAYER_DIR/python" -type f -name "*.txt" -delete

# 移除範例檔案
find "$LAYER_DIR/python" -type d -name "examples" -exec rm -rf {} +
```

**節省空間**:
- 測試檔案：~20MB
- 文件檔案：~10MB
- __pycache__：~5MB
- 總計：~35MB

## 📈 建置時間比較

### 第一次建置（無快取）

**標準版**:
```
下載依賴: 5 分鐘
安裝依賴: 3 分鐘
複製程式碼: 10 秒
打包 zip: 30 秒
─────────────────
總計: ~9 分鐘
```

**優化版**:
```
下載依賴: 2 分鐘（較少套件）
安裝依賴: 1 分鐘
複製程式碼: 10 秒
打包 zip: 20 秒（較小）
─────────────────
總計: ~3.5 分鐘
```

### 第二次建置（有快取，依賴沒變）

**標準版**:
```
下載依賴: 5 分鐘（重新下載）
安裝依賴: 3 分鐘
複製程式碼: 10 秒
打包 zip: 30 秒
─────────────────
總計: ~9 分鐘
```

**優化版**:
```
檢查快取: 1 秒
重複使用 layer: 0 秒（跳過安裝）
複製程式碼: 10 秒
打包 zip: 20 秒
─────────────────
總計: ~30 秒 ⚡
```

### 第二次建置（有快取，依賴有變）

**優化版**:
```
檢查快取: 1 秒
從快取安裝: 1 分鐘（不用下載）
複製程式碼: 10 秒
打包 zip: 20 秒
─────────────────
總計: ~1.5 分鐘
```

## 🔍 快取管理

### 查看快取狀態

```bash
cd deployment

# 查看快取大小
du -sh build/.pip-cache

# 查看依賴 hash
cat build/.deps_hash

# 查看已安裝的套件
ls -lh build/lambda_layer/python/
```

### 清除快取

```bash
cd deployment

# 清除 pip 快取（強制重新下載）
rm -rf build/.pip-cache

# 清除依賴 hash（強制重新安裝）
rm -f build/.deps_hash

# 清除所有建置檔案
rm -rf build/
rm -f lambda-layer.zip aws-ops-agent-function.zip
```

### 強制重新建置

```bash
cd deployment

# 方法 1: 清除快取後建置
rm -rf build/
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

# 方法 2: 修改 requirements-lambda.txt
# 加入或移除一個套件，hash 會改變，自動重新安裝
```

## 🎯 最佳實踐

### 1. 開發時使用快取

```bash
# 快速迭代開發
cd deployment
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

**優點**:
- 建置快速（< 30 秒）
- 節省時間
- 節省網路流量

### 2. CI/CD 使用快取

```yaml
# GitHub Actions 範例
- name: Cache pip dependencies
  uses: actions/cache@v3
  with:
    path: deployment/build/.pip-cache
    key: ${{ runner.os }}-pip-${{ hashFiles('deployment/requirements-lambda.txt') }}

- name: Build Lambda package
  run: |
    cd deployment
    PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

### 3. 生產部署前清除快取

```bash
# 確保使用最新版本
cd deployment
rm -rf build/
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

**原因**:
- 確保沒有快取的舊版本
- 確保所有依賴都是最新的
- 避免潛在的版本衝突

### 4. 定期更新依賴

```bash
# 更新 requirements-lambda.txt
cd deployment
pip3 list --outdated

# 更新特定套件
# 編輯 requirements-lambda.txt，修改版本號

# 重新建置
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

## 📊 監控建置

### 查看建置日誌

```bash
cd deployment
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh 2>&1 | tee build.log
```

### 檢查套件大小

```bash
cd deployment

# 查看 layer 大小
du -sh build/lambda_layer/
du -sh lambda-layer.zip

# 查看 function 大小
du -sh build/lambda_package/
du -sh aws-ops-agent-function.zip

# 檢查是否超過 Lambda 限制
layer_size=$(du -sm build/lambda_layer | cut -f1)
if [ "$layer_size" -gt 250 ]; then
    echo "⚠️  Layer 超過 250MB 限制: ${layer_size}MB"
else
    echo "✅ Layer 在限制內: ${layer_size}MB"
fi
```

### 查看已安裝的套件

```bash
cd deployment

# 列出所有套件
find build/lambda_layer/python -maxdepth 2 -name "*.dist-info" -type d

# 計算套件數量
find build/lambda_layer/python -maxdepth 2 -name "*.dist-info" -type d | wc -l

# 查看最大的套件
du -sh build/lambda_layer/python/* | sort -rh | head -10
```

## 🐛 故障排除

### 問題 1: 快取損壞

**症狀**:
```
ERROR: Could not find a version that satisfies the requirement...
```

**解決**:
```bash
# 清除快取
rm -rf build/.pip-cache
rm -rf build/lambda_layer

# 重新建置
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

### 問題 2: 依賴衝突

**症狀**:
```
ERROR: pip's dependency resolver does not currently take into account...
```

**解決**:
```bash
# 檢查 requirements-lambda.txt
cat requirements-lambda.txt

# 固定版本號
# 編輯 requirements-lambda.txt，指定確切版本
langchain-core==0.1.10  # 而不是 langchain-core>=0.1.0

# 重新建置
rm -rf build/
PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
```

### 問題 3: 建置太慢

**檢查**:
```bash
# 確認使用快取
echo $PIP_CACHE_DIR

# 確認快取存在
ls -lh build/.pip-cache

# 確認依賴沒變
cat build/.deps_hash
sha256sum requirements-lambda.txt
```

**優化**:
```bash
# 使用更快的 mirror
pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 或在建置時指定
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
PIP_CACHE_DIR=build/.pip-cache \
bash build_package_optimized.sh
```

## 📚 相關文件

- `build_package_optimized.sh` - 優化建置腳本
- `requirements-lambda.txt` - 生產依賴清單
- `LAMBDA_LAYER_OPTIMIZATION.md` - Layer 優化指南
- `deploy_teams_webhook.sh` - 部署腳本（使用優化建置）

## 🎓 進階技巧

### 1. 並行建置

```bash
# 同時建置 layer 和 function
(cd deployment && PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh) &
# 其他準備工作...
wait
```

### 2. 條件建置

```bash
# 只在依賴變更時建置
if [ "$(sha256sum requirements-lambda.txt)" != "$(cat build/.deps_hash)" ]; then
    echo "Dependencies changed, rebuilding..."
    PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh
else
    echo "Dependencies unchanged, skipping build"
fi
```

### 3. 多環境建置

```bash
# 開發環境（快速）
ENV=dev PIP_CACHE_DIR=build/.pip-cache bash build_package_optimized.sh

# 生產環境（完整）
ENV=prod bash build_package_optimized.sh
```

---

**總結**: 使用優化建置腳本可以大幅減少建置時間（從 9 分鐘降到 30 秒）和套件大小（從 150MB 降到 80MB），特別適合頻繁部署的開發環境。
