# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

家具報價單自動化系統 - 上傳 BOQ（Bill of Quantities）PDF 檔案，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單。

**API 基礎路徑**: `/api/v1/`（版本化 API）

### 核心功能（2025-12-23 更新）

1. **跨表合併**：支援上傳多個 PDF（數量總表 + 明細規格表），自動合併產出報價單
2. **自動角色偵測**：依檔名關鍵字偵測 PDF 角色（`qty`, `overall`, `summary` → 數量總表）
3. **智慧欄位合併**：多明細表依上傳順序優先合併，圖片選擇最高解析度
4. **合併報告**：詳細記錄每個項目的合併狀態與來源追蹤

## 常用開發指令

### 後端 (FastAPI)

```bash
# 安裝依賴
cd backend
pip install -r requirements.txt
pip install -e ".[dev]"  # 安裝開發依賴

# 啟動開發伺服器
cd backend
uvicorn app.main:app --reload

# 執行測試
cd backend
pytest                              # 所有測試（含覆蓋率，預設開啟）
pytest tests/unit/                  # 單元測試
pytest tests/integration/           # 整合測試
pytest tests/contract/              # 契約測試（API）
pytest -k "test_specific_name"      # 執行特定測試
pytest -v --cov-report=term-missing # 覆蓋率報告

# 程式碼品質
cd backend
ruff check .           # 檢查
ruff check . --fix     # 自動修復
black .                # 格式化（行寬 100）
```

### 前端 (Streamlit)

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### 環境設定

複製 `.env.example` 為 `.env`，設定必要環境變數：
- `GEMINI_API_KEY`: Google Gemini AI API 金鑰（必要）
- `GEMINI_MODEL`: Gemini 模型（預設 `gemini-3-flash-preview`）
- `GOOGLE_CREDENTIALS_PATH`: Google Service Account JSON 檔案路徑（選用）
- `GOOGLE_SHEETS_ENABLED`: 啟用 Google Sheets 功能（`true`/`false`）
- `GOOGLE_SHEETS_MASTER_ID`: Master spreadsheet ID（新增 Sheets 頁籤至此）
- `GOOGLE_DRIVE_FOLDER_ID`: Google Drive 資料夾 ID（圖片上傳用）

### 非協商性標準（來自 constitution.md）

- **測試優先開發**: 編寫測試 → 驗證失敗 → 實作 → 驗證通過
- **最低 80% 覆蓋率**（關鍵路徑 100%）
- **API 回應時間**: < 200ms (p95)，PDF 解析 < 15 秒

## 架構概述

### 資料流程

#### 單一 PDF 模式
1. **上傳**: 使用者上傳 PDF → `upload.py` 路由 → 儲存檔案 + 建立 `SourceDocument`
2. **解析**: `parse.py` 路由 → `PDFParserService` 呼叫 Gemini AI → 提取 `BOQItem` 列表 + 圖片（確定性匹配）
3. **匯出**: `export.py` 路由 → `ExcelGeneratorService` → 產出惠而蒙格式 Excel

#### 跨表合併模式（2025-12-23 新增）
1. **上傳多個 PDF**: 使用者上傳多個 PDF → `upload.py` 路由 → 儲存檔案 + 偵測角色（`DocumentRoleDetector`）
2. **分別解析**:
   - 數量總表 → `QuantitySummaryParser` → 提取 `QuantitySummaryItem[]` (Item No. + Total Qty)
   - 明細規格表 → `PDFParserService` → 提取 `BOQItem[]` (完整 15 欄)
3. **跨表合併**: `MergeService` →
   - Item No. 標準化（大寫、去空格、統一分隔符）
   - 建立數量索引，依 Item No. 配對
   - 多明細表欄位依 `upload_order` 優先合併
   - 圖片選擇最高解析度
   - 產出 `MergeReport` + 合併後 `BOQItem[]`
4. **匯出**: `export.py` 路由 → `ExcelGeneratorService` → 產出惠而蒙格式 Excel

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
│   ├── boq_item.py                 # BOQItem 模型（15 欄 Excel + 8 欄內部追蹤）
│   ├── responses.py                # BOQItemResponse DTO（15 欄，隱藏內部追蹤欄位）
│   ├── merge_report.py             # MergeReport, MergeResult 跨表合併報告
│   ├── quantity_summary.py         # QuantitySummaryItem 數量總表項目
│   └── ...                         # SourceDocument, Quotation, ProcessingTask
├── services/
│   ├── pdf_parser.py               # PDF 解析（Gemini AI）
│   ├── image_extractor.py          # PDF 圖片提取
│   ├── image_matcher_deterministic.py  # 確定性圖片-項目匹配
│   ├── excel_generator.py          # Excel 產出（惠而蒙格式）
│   ├── document_role_detector.py   # 文件角色偵測（依檔名關鍵字）
│   ├── item_normalizer.py          # Item No. 標準化（大寫、去空格、統一分隔符）
│   ├── merge_service.py            # 跨表合併服務
│   ├── image_selector.py           # 圖片解析度選擇（最高解析度優先）
│   ├── dimension_formatter.py      # 尺寸格式化
│   └── quotation_format.py         # 報價單格式處理
├── api/routes/                      # 所有路由使用 /api/v1/ 前綴
│   ├── upload.py                   # POST /documents, GET /documents/{id}
│   ├── parse.py                    # POST /documents/{id}/parsing
│   ├── export.py                   # POST /quotations, GET /quotations/{id}/excel
│   ├── merge.py                    # POST /quotations/merge, GET /quotations/{id}/merge-report
│   ├── sheets.py                   # POST/GET /quotations/{id}/sheets, GET /sheets/status
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
- **Gemini AI**: 需設定 `GEMINI_API_KEY`，僅用於 PDF 解析（預設 `gemini-3-flash-preview` 模型）
- **檔案限制**: 單檔最大 50MB，每次上傳最多 10 個檔案，總頁數 ≤ 200
- **價格欄位**: Unit Rate (H欄)、Amount (I欄) 留空由使用者填寫
- **圖片匹配**: 僅使用確定性演算法，不使用 Vision API
- **跨表合併**: 每次最多 1 個數量總表，多明細表依上傳順序合併
- **Google Sheets**: 暫不實作（Out of Scope）

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

### Response DTO 模式

- `BOQItem`（內部）: 15 欄 Excel 欄位 + 8 欄內部追蹤欄位（`source_type`, `qty_verified`, `qty_source`, `item_no_normalized`, `source_files`, `merge_status`, `qty_from_summary`, `image_selected_from`）
- `BOQItemResponse`（外部 API）: 15 欄位 DTO，隱藏內部追蹤欄位
- API 回傳項目時使用 `BOQItemResponse.from_boq_item(item)` 轉換

### 狀態管理

- **後端**: 所有狀態存於 `store.py`（InMemoryStore 單例），使用 `cachetools.TTLCache`（1 小時 TTL）
- **前端**: Streamlit `st.session_state` 管理工作流程（`upload` → `processing` → `download`）
- 背景任務使用 `ProcessingTask` 模型追蹤狀態

### 錯誤處理

- `ErrorCode` 列舉定義所有錯誤碼（`utils/errors.py`）
- 使用 `raise_error(ErrorCode.XXX, "訊息", status_code=404)` 拋出 API 錯誤
- 錯誤訊息統一使用繁體中文（`ERROR_MESSAGES` 字典）

### 測試策略

- **單元測試**: 獨立測試服務行為（`tests/unit/`）
- **整合測試**: 完整上傳/解析流程（`tests/integration/`）
- **契約測試**: API 請求/回應驗證（`tests/contract/`）
- pytest markers: `@pytest.mark.unit`, `.integration`, `.contract`, `.slow`
- **測試 fixtures** (`tests/conftest.py`): `client`（TestClient）、`mock_store`、`sample_pdf_file`、`sample_boq_item_data`
- **API 前綴常數**: `API_PREFIX = "/api/v1"`（定義於 conftest.py）

## 規格文件

- 功能規格：`specs/001-furniture-quotation-system/spec.md`
- 實作計畫：`specs/001-furniture-quotation-system/plan.md`
- 資料模型：`specs/001-furniture-quotation-system/data-model.md`
- OpenAPI 契約：`specs/001-furniture-quotation-system/contracts/openapi.yaml`
- 圖片匹配說明：`backend/docs/DETERMINISTIC_IMAGE_MATCHING.md`

## API 端點快速參考

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/documents` | POST | 上傳 PDF，自動偵測角色並啟動解析 |
| `/api/v1/documents/{id}` | GET | 取得文件詳情（含 `document_role`） |
| `/api/v1/documents/{id}/parsing` | POST | 啟動解析（若未自動啟動） |
| `/api/v1/documents/{id}/parse-result` | GET | 取得解析後的 BOQ 項目 |
| `/api/v1/quotations` | POST | 從文件建立報價單（單一 PDF 模式） |
| `/api/v1/quotations/merge` | POST | **[新增]** 跨表合併報價單（多 PDF 模式） |
| `/api/v1/quotations/{id}/items` | GET | 取得報價單項目 |
| `/api/v1/quotations/{id}/excel` | GET | 下載 Excel（產出中回傳 202） |
| `/api/v1/quotations/{id}/merge-report` | GET | **[新增]** 取得跨表合併報告 |
| `/api/v1/tasks/{id}` | GET | 查詢背景任務狀態 |

### 跨表合併 API 使用範例

```bash
# 1. 上傳多個 PDF
curl -X POST /api/v1/documents \
  -F "files=@Bay Tower...Qty.pdf" \
  -F "files=@Casegoods.pdf" \
  -F "files=@Fabric.pdf"

# 2. 建立跨表合併報價單
curl -X POST /api/v1/quotations/merge \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["doc1", "doc2", "doc3"], "title": "Bay Tower 報價單"}'

# 3. 查看合併報告
curl /api/v1/quotations/{id}/merge-report

# 4. 下載 Excel
curl -O /api/v1/quotations/{id}/excel
```
