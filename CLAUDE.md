# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

家具報價單自動化系統 - 上傳 BOQ（Bill of Quantities）PDF 檔案，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單。

**API 基礎路徑**: `/api/v1/`（版本化 API）

## 常用開發指令

### 後端 (FastAPI)

```bash
# 安裝依賴
cd backend && pip install -r requirements.txt
pip install -e ".[dev]"  # 安裝開發依賴

# 啟動開發伺服器
cd backend && uvicorn app.main:app --reload

# 執行測試
cd backend && pytest                          # 所有測試（含覆蓋率）
cd backend && pytest tests/unit/              # 單元測試
cd backend && pytest tests/integration/       # 整合測試
cd backend && pytest tests/contract/          # 契約測試（API）
cd backend && pytest -k "test_specific_name"  # 執行特定測試
cd backend && pytest -v --cov=app --cov-report=term-missing  # 覆蓋率報告

# 程式碼品質
cd backend && ruff check .                    # 檢查
cd backend && ruff check . --fix              # 自動修復
cd backend && black .                         # 格式化（行寬 100）
```

### 前端 (Streamlit)

```bash
# 安裝依賴
cd frontend && pip install -r requirements.txt

# 啟動開發伺服器
cd frontend && streamlit run app.py
```

### 環境設定

複製 `.env.example` 為 `.env`，設定 `GEMINI_API_KEY`。

## 架構概述

### 資料流程

1. **上傳**: 使用者上傳 PDF → `upload.py` 路由 → 儲存檔案 + 建立 `SourceDocument`
2. **解析**: `parse.py` 路由 → `PDFParserService` 呼叫 Gemini AI → 提取 `BOQItem` 列表 + 圖片（確定性匹配）
3. **匯出**: `export.py` 路由 → `ExcelGeneratorService` → 產出惠而蒙格式 Excel

### 關鍵架構模式

- **記憶體儲存** (`store.py`): 單例 `InMemoryStore` 搭配 TTL 快取（1 小時）。所有狀態（文件、BOQ 項目、報價單、任務、圖片）存於記憶體，無資料庫。
- **服務層**: 業務邏輯位於 `backend/app/services/`，每個服務為單例，透過 `get_*()` 工廠函式取得。
- **依賴注入**: `backend/app/api/dependencies.py` 提供 `StoreDep`、`FileManagerDep`、`FileValidatorDep` 供路由使用。
- **錯誤處理**: 自訂 `APIError` 搭配 `ErrorCode` 列舉，繁體中文錯誤訊息，集中於 `main.py` 處理。

### 後端結構

```
backend/app/
├── main.py                          # FastAPI 應用、生命週期、錯誤處理
├── config.py                        # Pydantic Settings 環境設定
├── store.py                         # InMemoryStore 單例（TTL 快取）
├── models/
│   ├── boq_item.py                 # BOQItem 模型（23 欄位）
│   ├── responses.py                # BOQItemResponse DTO（隱藏內部欄位）
│   └── ...                         # SourceDocument, Quotation, ProcessingTask
├── services/
│   ├── pdf_parser.py               # PDF 解析（Gemini AI）
│   ├── image_extractor.py          # PDF 圖片提取
│   ├── image_matcher_deterministic.py  # 確定性圖片-項目匹配
│   └── excel_generator.py          # Excel 產出（惠而蒙格式）
├── api/routes/                      # 所有路由使用 /api/v1/ 前綴
│   ├── upload.py                   # POST /documents, GET /documents/{id}
│   ├── parse.py                    # POST /documents/{id}/parsing
│   ├── export.py                   # POST /quotations, GET /quotations/{id}/excel
│   ├── task.py                     # GET /tasks/{id}
│   └── health.py                   # GET /health
└── utils/                           # 錯誤處理、檔案管理、驗證
```

### 前端結構

```
frontend/
├── app.py                           # Streamlit 主程式、頁面路由、session state
├── services/api_client.py          # 非同步 HTTP 客戶端（連接後端）
├── components/                      # 可重用 UI 元件
└── pages/                          # 頁面實作
```

### 圖片匹配系統

系統使用**確定性圖片-項目匹配**（非 Vision API）以確保可靠性和成本效益：

- **位置**: `backend/app/services/image_matcher_deterministic.py`
- **演算法**: 頁面偏移匹配（第 N 頁圖片匹配第 N-1 頁項目）
- **Logo 過濾**: 自動過濾小圖片（< 10,000 px²）避免匹配到 Logo/頁首
- **效能**: 每份 PDF < 100ms（相比 Vision API 需 10-15 秒）
- **測試**: `backend/tests/unit/test_image_matcher_deterministic.py`（18 個測試，100% 覆蓋率）

## 技術限制

- **無 Redis/資料庫**: 檔案存於檔案系統，狀態存於記憶體（1 小時 TTL 快取）
- **Gemini AI**: 需設定 `GEMINI_API_KEY`，僅用於 PDF 解析（使用 `gemini-1.5-flash` 模型）
- **檔案限制**: 單檔最大 50MB，每次上傳最多 5 個檔案
- **價格欄位**: Unit Rate (H欄)、Amount (I欄) 留空由使用者填寫
- **圖片匹配**: 僅使用確定性演算法，不使用 Vision API

## 惠而蒙 Excel 格式（共 15 欄）

| 欄 | 欄位名稱 | 說明 |
|----|----------|------|
| A | NO. | 序號（系統自動產生） |
| B | Item no. | 項目編號 |
| C | Description | 品名描述 |
| D | Photo | 圖片（Base64 嵌入） |
| E | Dimension WxDxH (mm) | 尺寸規格 |
| F | Qty | 數量 |
| G | UOM | 單位 |
| H | Unit Rate (USD) | 單價（**留空**，使用者填寫） |
| I | Amount (USD) | 金額（**留空**，使用者填寫） |
| J | Unit CBM | 單位材積 |
| K | Total CBM | 總材積（公式 =F*J） |
| L | Note | 備註 |
| M | Location | 位置 |
| N | Materials Used / Specs | 材料/規格 |
| O | Brand | 品牌 |

範例檔案：`docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`

## 程式碼規範

- Python 3.11+，必須使用 type hints
- ruff + black（行寬 100）
- 公開 API 必須有 docstrings
- 錯誤訊息使用繁體中文
- 測試覆蓋率 >= 80%
- API 回應時間 < 200ms（標準請求）

## 關鍵檔案與模式

### 重要服務

- `pdf_parser.py`: 使用 Gemini 從 PDF 提取 BOQ 資料
- `image_matcher_deterministic.py`: 使用確定性規則匹配圖片到項目（頁面偏移 + 面積過濾）
- `excel_generator.py`: 從 BOQ 項目產出惠而蒙格式 Excel

### Response DTO 模式

- `BOQItem`（內部）: 完整 23 欄位模型，含追蹤欄位
- `BOQItemResponse`（外部 API）: 15 欄位 DTO，隱藏內部欄位（`source_type`, `qty_verified`, `qty_source`, `created_at`, `updated_at`）
- API 回傳項目時使用 `BOQItemResponse.from_boq_item(item)` 轉換

### 狀態管理

- 所有狀態存於 `store.py`（InMemoryStore 單例）
- 背景任務使用 `ProcessingTask` 模型追蹤狀態

### 測試策略

- **單元測試**: 獨立測試服務行為
- **整合測試**: 完整上傳/解析流程
- **契約測試**: API 請求/回應驗證
- 測試使用 pytest markers（`@pytest.mark.unit`, `.integration`, `.contract`）

## 規格文件

- 功能規格：`specs/001-furniture-quotation-system/spec.md`
- 實作計畫：`specs/001-furniture-quotation-system/plan.md`
- 資料模型：`specs/001-furniture-quotation-system/data-model.md`
- OpenAPI 契約：`specs/001-furniture-quotation-system/contracts/openapi.yaml`
- 圖片匹配說明：`backend/docs/DETERMINISTIC_IMAGE_MATCHING.md`

## API 端點快速參考

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/documents` | POST | 上傳 PDF，自動啟動解析 |
| `/api/v1/documents/{id}` | GET | 取得文件詳情 |
| `/api/v1/documents/{id}/parsing` | POST | 啟動解析（若未自動啟動） |
| `/api/v1/documents/{id}/parse-result` | GET | 取得解析後的 BOQ 項目 |
| `/api/v1/quotations` | POST | 從文件建立報價單 |
| `/api/v1/quotations/{id}/items` | GET | 取得報價單項目 |
| `/api/v1/quotations/{id}/excel` | GET | 下載 Excel（產出中回傳 202） |
| `/api/v1/tasks/{id}` | GET | 查詢背景任務狀態 |
