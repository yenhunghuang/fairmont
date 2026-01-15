# Fairmont 家具報價單自動化系統

上傳 BOQ (Bill of Quantities) PDF，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單。

![流程簡介](docs/assets/flow-overview.png)

## 功能特色

- **PDF 智慧解析** - Gemini AI 提取家具規格、面料資訊
- **跨表合併** - 自動比對數量總表與明細規格表
- **圖片匹配** - 確定性演算法配對產品圖片
- **Excel 輸出** - 符合客戶 15 欄報價單格式

## 快速開始

### 環境需求

- Python >= 3.11
- Docker (可選)

### 環境變數

```bash
# .env (必填)
GEMINI_API_KEY=your_gemini_api_key
API_KEY=your_api_key

# Langfuse 可觀測性 (選用)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 啟動服務

```bash
# Docker
docker-compose up -d --build

# 或本地開發
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### API 使用

```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "files=@your-file.pdf"
```

**Swagger UI**: http://localhost:8000/docs

## 測試文件

專案包含 Fairmont 測試用文件，位於 `docs/assets/fairmont-docs/`：

| 檔案 | 說明 |
|------|------|
| `Overall_QTY.pdf` | 數量總表 - 包含所有項目編號與總數量 |
| `Casegoods & Seatings.pdf` | 家具規格 - 木製家具與座椅詳細規格 |
| `Fabric & Leather.pdf` | 面料規格 - 布料與皮革材質規格 |
| `RFQ FORM-FTQ25106_報價Excel Form.xlsx` | 報價表範本 - 客戶期望的輸出格式 |

### 使用測試文件

```bash
curl -X POST "http://localhost:8001/api/v1/process" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "files=@docs/assets/fairmont-docs/Overall_QTY.pdf" \
  -F "files=@docs/assets/fairmont-docs/Casegoods & Seatings.pdf" \
  -F "files=@docs/assets/fairmont-docs/Fabric & Leather.pdf" \
  --max-time 360
```

## 技術架構

| 元件 | 技術 |
|------|------|
| 後端 | FastAPI + Python 3.11 |
| AI | Google Gemini 2.0 Flash |
| 配置 | Skills YAML (供應商/輸出格式/合併規則) |
| 儲存 | 記憶體快取 (1hr TTL) |

詳見 [架構文件](docs/architecture-flow.md)

## 專案結構

```
backend/
├── app/
│   ├── api/routes/      # API 端點
│   ├── services/        # 業務邏輯
│   └── models/          # 資料模型
skills/
├── vendors/             # 供應商配置
├── output-formats/      # 輸出格式
└── core/                # 合併規則
```

## 測試機部署

### 部署腳本 (Windows PowerShell)

使用 `deploy.ps1` 一鍵部署到測試機 `192.168.0.83`：

```powershell
# 在本機執行
.\deploy.ps1
```

### 手動部署步驟

**目標伺服器**: `ai-user@192.168.0.83`
**遠端目錄**: `/home/ai-user/Fairmont`

#### 1. 上傳檔案

```bash
scp -r backend skills docker-compose.yml .env.example ai-user@192.168.0.83:/home/ai-user/Fairmont/
```

#### 2. SSH 連線到伺服器

```bash
ssh ai-user@192.168.0.83
```

#### 3. 安裝 Docker (如尚未安裝)

```bash
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
# 重新登入以套用群組變更
```

#### 4. 設定環境變數

```bash
cd ~/Fairmont
cp .env.example .env
nano .env  # 填入 GEMINI_API_KEY 和 API_KEY
```

**.env 必填項目**:
```env
GEMINI_API_KEY=your_gemini_api_key
API_KEY=your_api_key
```

#### 5. 啟動服務

```bash
docker-compose up -d --build
```

#### 6. 驗證

```bash
curl http://localhost:8001/api/v1/health
```

**Swagger UI**: http://192.168.0.83:8001/docs

### 常用指令

```bash
# 查看日誌
docker-compose logs -f backend

# 重啟服務
docker-compose restart

# 停止服務
docker-compose down

# 重新部署
docker-compose down && docker-compose up -d --build
```

## 文件

- [CLAUDE.md](CLAUDE.md) - 開發指引
- [架構流程](docs/architecture-flow.md)
- [部署說明](docs/deployment.md)
- [前端 API](docs/frontend-api.md)
