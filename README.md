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

## 文件

- [CLAUDE.md](CLAUDE.md) - 開發指引
- [架構流程](docs/architecture-flow.md)
- [部署說明](docs/deployment.md)
- [前端 API](docs/frontend-api.md)
