# CLAUDE.md

本檔案為 Claude Code (claude.ai/code) 在此專案中工作時的指引文件。

## 專案概述

家具報價單自動化系統 - 上傳 BOQ（Bill of Quantities）PDF 檔案，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單。

## 開發指令

### 後端 (FastAPI)

```bash
# 安裝依賴
cd backend && pip install -r requirements.txt
pip install -e ".[dev]"  # 安裝開發依賴

# 啟動伺服器
cd backend && uvicorn app.main:app --reload

# 執行測試
cd backend && pytest                          # 所有測試（含覆蓋率）
cd backend && pytest tests/unit/              # 單元測試
cd backend && pytest tests/integration/       # 整合測試
cd backend && pytest tests/contract/          # 契約測試
cd backend && pytest -k "test_function_name"  # 單一測試
cd backend && pytest -v --cov=app --cov-report=term-missing  # 覆蓋率報告

# 程式碼檢查與格式化
cd backend && ruff check .                    # 檢查
cd backend && ruff check . --fix              # 自動修復
cd backend && black .                         # 格式化
```

### 前端 (Streamlit)

```bash
# 安裝依賴
cd frontend && pip install -r requirements.txt

# 啟動應用
cd frontend && streamlit run app.py
```

### 環境設定

複製 `.env.example` 為 `.env`，設定 `GEMINI_API_KEY`。

## 架構說明

### 資料流程

1. **上傳**: 使用者上傳 PDF → `upload.py` 路由 → 儲存檔案 + 建立 `SourceDocument`
2. **解析**: `parse.py` 路由 → `PDFParserService` 呼叫 Gemini AI → 提取 `BOQItem` 列表 + 圖片
3. **匯出**: `export.py` 路由 → `ExcelGeneratorService` → 產出惠而蒙格式 Excel

### 關鍵架構模式

- **記憶體儲存** (`store.py`): 單例 `InMemoryStore` 搭配 TTL 快取，無資料庫。所有狀態（文件、BOQ 項目、報價單、任務、圖片）存於記憶體。
- **服務層**: 業務邏輯位於 `backend/app/services/`，每個服務為單例，透過 `get_*()` 工廠函式取得。
- **依賴注入**: `backend/app/api/dependencies.py` 提供 `StoreDep`、`FileManagerDep`、`FileValidatorDep` 供路由使用。
- **錯誤處理**: 自訂 `APIError` 搭配 `ErrorCode` 列舉，繁體中文錯誤訊息，集中於 `main.py` 處理。

### 後端結構

```
backend/app/
├── main.py           # FastAPI 應用、生命週期、錯誤處理、路由註冊
├── config.py         # 環境設定（Pydantic Settings）
├── store.py          # InMemoryStore（文件、BOQ 項目、報價單、任務、圖片）
├── models/           # Pydantic 模型：BOQItem, SourceDocument, Quotation, ProcessingTask, ExtractedImage
├── services/         # 業務邏輯：pdf_parser, image_extractor, excel_generator
├── api/routes/       # FastAPI 路由：upload, parse, export, task, health
└── utils/            # 錯誤處理、檔案管理、驗證器
```

### 前端結構

```
frontend/
├── app.py            # Streamlit 主程式、頁面路由、session state 初始化
├── services/         # api_client.py（httpx 非同步客戶端連接後端）
├── components/       # 可重用 UI 元件：file_uploader, material_table, progress_display
└── pages/            # upload.py, preview.py
```

## 技術限制

- **無 Redis/資料庫**: 檔案系統暫存檔案，記憶體儲存狀態（1 小時 TTL 快取）
- **Gemini AI**: 需設定 `GEMINI_API_KEY` 環境變數，使用 `gemini-1.5-flash` 模型
- **檔案限制**: 單檔最大 50MB，最多 5 個檔案
- **價格欄位排除**: Unit Rate、Amount、CBM 由使用者手動填寫，系統不產生

## 惠而蒙 Excel 格式

10 欄（A-J）：NO.、Item No.、Description、Photo、Dimension（WxDxH mm）、Qty、UOM、Note、Location、Materials Used/Specs

範例檔案：`docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`

## 程式碼規範

- Python 3.11+，必須使用 type hints
- ruff + black 檢查/格式化（行寬 100）
- 公開 API 必須有 docstrings
- 錯誤訊息使用繁體中文
- 測試覆蓋率 >= 80%，測試優先開發
- API 回應時間 < 200ms（標準請求）

## 規格文件

- 功能規格：`specs/001-furniture-quotation-system/spec.md`
- 實作計畫：`specs/001-furniture-quotation-system/plan.md`
- 資料模型：`specs/001-furniture-quotation-system/data-model.md`
- API 契約：`specs/001-furniture-quotation-system/contracts/openapi.yaml`
