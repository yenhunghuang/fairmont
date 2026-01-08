# 快速開始指南：家具報價單系統

**Feature Branch**: `001-furniture-quotation-system`
**Date**: 2025-12-19
**Updated**: 2025-12-23 - 新增跨表合併功能

## 系統需求

- Python 3.11+
- pip 或 uv（套件管理）
- Google Gemini API Key

## 1. 環境設定

### 1.1 複製專案

```bash
git clone <repository-url>
cd Fairmont
git checkout 001-furniture-quotation-system
```

### 1.2 設定環境變數

建立 `.env` 檔案：

```bash
cp .env.example .env
```

編輯 `.env` 填入 Gemini API Key：

```env
# Gemini API 設定
GEMINI_API_KEY=your-gemini-api-key-here

# 後端設定
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# 前端設定
FRONTEND_PORT=8501

# 暫存檔案設定
TEMP_DIR=./temp
MAX_FILE_SIZE_MB=50
TEMP_FILE_MAX_AGE_HOURS=24
```

### 1.3 安裝後端依賴

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 1.4 安裝前端依賴

```bash
cd frontend
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

## 2. 啟動服務

### 2.1 啟動後端 API

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

後端 API 將在 http://localhost:8000 運行。
API 文件：http://localhost:8000/docs

### 2.2 啟動前端 UI

開啟新的終端機視窗：

```bash
cd frontend
streamlit run app.py --server.port 8501
```

前端 UI 將在 http://localhost:8501 運行。

## 3. 使用 Docker（替代方案）

### 3.1 使用 Docker Compose

```bash
# 建構並啟動所有服務
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

服務端口：
- 前端 UI：http://localhost:8501
- 後端 API：http://localhost:8000

## 4. 基本使用流程

### 4.1 上傳 PDF（跨表合併模式）

**新功能**：支援上傳多個 PDF 進行跨表合併

1. 開啟瀏覽器訪問 http://localhost:8501
2. 點擊「選擇 PDF 檔案」按鈕
3. 選擇多個 PDF 檔案（最多 10 個，每個最大 50MB，總頁數 ≤ 200）
   - **數量總表**：檔名含 `qty`, `overall`, `summary`, `數量`, `總量`, `總表`
   - **明細規格表**：其他 PDF 檔案
4. 點擊「開始處理」

**範例上傳**：
- `Bay Tower Furniture - Overall Qty.pdf`（數量總表）
- `Casegoods & Seatings.pdf`（明細規格表 #1）
- `Fabric & Leather.pdf`（明細規格表 #2）

### 4.2 等待解析與合併

系統將：
1. 上傳檔案到伺服器
2. **自動偵測文件角色**（依檔名關鍵字）
3. 解析數量總表（提取 Item No. + Total Qty）
4. 解析明細規格表（提取完整 15 欄）
5. **跨表合併**：
   - 依 Item No. 配對項目
   - 用數量總表的 qty 覆蓋明細表
   - 多明細表欄位依上傳順序優先合併
   - 圖片選擇最高解析度
6. 顯示即時進度

### 4.3 預覽結果

解析完成後：
1. 檢視材料表格（15 欄惠而蒙格式）
2. 查看**合併報告**：
   - 配對成功的項目（綠色）
   - 未配對的項目（黃色警告）
   - 僅在數量總表的項目（灰色）
3. 確認圖片是否正確配對
4. 修正任何解析錯誤

### 4.4 下載 Excel

1. 點擊「下載 Excel」按鈕
2. 系統產出惠而蒙格式報價單（15 欄）
3. 儲存 .xlsx 檔案

## 5. API 快速測試

### 5.1 健康檢查

```bash
curl http://localhost:8000/
```

回應：
```json
{
  "status": "ok",
  "message": "服務運行中",
  "timestamp": "2025-12-19T10:00:00"
}
```

### 5.2 上傳多個 PDF（跨表合併）

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "files=@Bay Tower Furniture - Overall Qty.pdf" \
  -F "files=@Casegoods & Seatings.pdf" \
  -F "files=@Fabric & Leather.pdf"
```

回應：
```json
{
  "success": true,
  "documents": [
    {
      "document_id": "abc123...",
      "filename": "Bay Tower Furniture - Overall Qty.pdf",
      "document_role": "quantity_summary",
      "task_id": "def456..."
    },
    {
      "document_id": "bcd234...",
      "filename": "Casegoods & Seatings.pdf",
      "document_role": "detail_spec",
      "upload_order": 1,
      "task_id": "efg567..."
    },
    {
      "document_id": "cde345...",
      "filename": "Fabric & Leather.pdf",
      "document_role": "detail_spec",
      "upload_order": 2,
      "task_id": "fgh678..."
    }
  ],
  "message": "已成功上傳 3 個檔案"
}
```

### 5.3 查詢任務狀態

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

回應：
```json
{
  "task_id": "def456...",
  "task_type": "parse_pdf",
  "status": "processing",
  "progress": 60,
  "message": "正在解析 BOQ 表格..."
}
```

### 5.4 取得解析結果

```bash
curl http://localhost:8000/api/v1/documents/{document_id}/parse-result
```

### 5.5 建立跨表合併報價單（新功能）

```bash
curl -X POST http://localhost:8000/api/v1/quotations/merge \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["abc123...", "bcd234...", "cde345..."],
    "title": "Bay Tower 家具報價單"
  }'
```

回應：
```json
{
  "task_id": "merge-task-123...",
  "quotation_id": "quot-456...",
  "status": "processing",
  "message": "跨表合併任務已建立",
  "detected_roles": {
    "quantity_summary": {
      "document_id": "abc123...",
      "filename": "Bay Tower Furniture - Overall Qty.pdf"
    },
    "detail_specs": [
      {"document_id": "bcd234...", "filename": "Casegoods & Seatings.pdf", "upload_order": 1},
      {"document_id": "cde345...", "filename": "Fabric & Leather.pdf", "upload_order": 2}
    ]
  }
}
```

### 5.6 取得合併報告（新功能）

```bash
curl http://localhost:8000/api/v1/quotations/{quotation_id}/merge-report
```

回應：
```json
{
  "id": "report-789...",
  "quotation_id": "quot-456...",
  "total_items": 150,
  "matched_items": 142,
  "unmatched_items": 5,
  "quantity_only_items": 3,
  "match_rate": 94.67,
  "warnings": [
    "Item No. 'DLX-999' 僅在數量總表中出現，無明細規格",
    "Item No. 'FUR-123' 在明細表中未找到對應數量"
  ],
  "processing_time_ms": 2500
}
```

### 5.7 下載 Excel

```bash
curl -O http://localhost:8000/api/v1/quotations/{quotation_id}/excel
```

## 6. 開發指令

### 6.1 執行測試

```bash
# 後端單元測試
cd backend
pytest tests/unit -v

# 後端整合測試
pytest tests/integration -v

# 測試覆蓋率
pytest --cov=app --cov-report=html

# 前端 E2E 測試
cd frontend
pytest tests/e2e -v
```

### 6.2 程式碼檢查

```bash
# 格式化
black backend/app
black frontend

# Linting
ruff check backend/app
ruff check frontend
```

### 6.3 產生 API 文件

FastAPI 自動產生 OpenAPI 文件：
- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- OpenAPI JSON：http://localhost:8000/openapi.json

## 7. 故障排除

### 7.1 Gemini API 錯誤

**問題**：`API key not valid` 錯誤

**解決**：
1. 確認 `.env` 中的 `GEMINI_API_KEY` 正確
2. 確認 API Key 已啟用 Gemini API
3. 檢查 API 配額是否用盡

### 7.2 檔案上傳失敗

**問題**：`檔案大小超過限制` 錯誤

**解決**：
1. 確認檔案小於 50MB
2. 如需調整限制，修改 `.env` 中的 `MAX_FILE_SIZE_MB`

### 7.3 解析結果不準確

**問題**：BOQ 項目解析不完整

**解決**：
1. 確認 PDF 中的表格格式清晰
2. 嘗試調整 PDF 掃描品質
3. 檢查 PDF 是否加密或有密碼保護

### 7.4 圖片無法嵌入 Excel

**問題**：Excel 中圖片欄位為空

**解決**：
1. 確認 PDF 中有嵌入圖片（非純文字）
2. 檢查圖片是否過小被過濾（最小 100x100 px）
3. 確認暫存目錄有足夠空間

## 8. 目錄結構

```
Fairmont/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 設定
│   │   ├── models/           # 資料模型
│   │   ├── services/         # 業務邏輯
│   │   ├── api/routes/       # API 路由
│   │   └── utils/            # 工具函式
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Streamlit 入口
│   ├── pages/                # 頁面元件
│   ├── components/           # UI 元件
│   ├── services/             # API 客戶端
│   └── requirements.txt
├── specs/                    # 規格文件
├── .env.example
├── docker-compose.yml
└── README.md
```

## 9. 下一步

1. 閱讀 [spec.md](./spec.md) 了解完整功能規格
2. 閱讀 [data-model.md](./data-model.md) 了解資料模型
3. 查看 [contracts/openapi.yaml](./contracts/openapi.yaml) 了解 API 規格
4. 執行 `/speckit.tasks` 產生開發任務清單
