# 家具報價單自動化系統 (Gemini FF&E Quotation System)

## 專案概述
本專案是一個利用 Google Gemini AI 自動化處理家具報價單的系統。主要功能是將供應商提供的 BOQ (Bill of Quantities) PDF 檔案解析，並轉換成特定格式（惠而蒙 Fairmont 格式，共 15 欄）的 Excel 報價單。

### 核心流程
1. **上傳 PDF**: 使用者上傳家具規格書或數量總表。
2. **AI 解析**: 利用 gemini-3-flash-preview 模型提取品項編號、描述、尺寸、位置、材質等資訊。
3. **圖片匹配**: 使用確定性演算法（頁面偏移）自動匹配規格頁與其對應的產品圖片。
4. **合併與排序**: 自動將數量總表與規格明細合併，並根據特定規則（如面料跟隨家具）進行排序。
5. **導出 Excel**: 產出符合 15 欄位規範的 Excel 檔案。

## 技術棧
- **後端**: Python 3.11+, FastAPI, Pydantic, Uvicorn
- **前端**: Streamlit (POC 階段採用簡化的 Step-based 流程)
- **AI 模型**: Google Gemini 3.0 Flash Preview
- **PDF 處理**: PyMuPDF (fitz)
- **資料儲存**: InMemoryStore (具備 1 小時 TTL 的記憶體緩存，無資料庫)
- **品質控管**: Pytest, Ruff (Linter), Black (Formatter)
- **可觀測性**: Langfuse (可選)

## 快速開始

### 環境設定
在專案根目錄建立 `.env` 檔案：
```env
GEMINI_API_KEY=你的_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.0-flash-lite
SKILLS_DIR=skills/
```

### 啟動後端
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
後端預設運行在 `http://localhost:8000`。

### 啟動前端
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```
前端預設運行在 `http://localhost:8501`。

## 核心特性：Skills 配置化系統
本系統採用「配置驅動解析」(Configuration-driven Parsing) 的架構，透過 `skills/` 目錄下的 YAML 檔案來定義不同供應商的解析行為，而不需要修改核心代碼：

- **Vendor Skills**: 定義特定供應商（如 Habitus）的 PDF 結構、Prompt 模板、頁面偏移規則及圖片過濾標準。
- **Output Formats**: 定義 Excel 的輸出欄位、表頭樣式、公司資訊及條款。
- **Merge Rules**: 定義文件角色偵測（如：哪種文件是數量總表）、欄位合併策略（如：地點欄位使用逗號分隔）。

## 目錄結構
- `backend/`: FastAPI 應用程式核心代碼。
  - `app/api/`: API 路由定義（上傳、解析、合併、導出）。
  - `app/services/`: 核心業務邏輯（Gemini 解析、Excel 生成、圖片匹配、品項標準化）。
  - `app/models/`: Pydantic 資料模型與 DTO。
  - `app/store.py`: 具備 TTL 緩存的記憶體儲存單例。
- `frontend/`: Streamlit 前端應用程式。
- `skills/`: 基於 YAML 的配置系統。
  - `vendors/`: 供應商特定解析規則（如 `habitus.yaml`）。
  - `output-formats/`: 輸出 Excel 格式定義（如 `fairmont.yaml`）。
  - `core/`: 全域合併、排序與文件角色偵測規則。
- `specs/`: 詳細的功能規格、資料模型與 OpenAPI 契約。
- `docs/`: 架構圖、流程圖、範例文件及 POC 階段性報告。

## 開發規範
- **測試驅動 (TDD)**: 新功能需附帶單元測試或整合測試，目標覆蓋率 >= 80%。
- **程式碼風格**: 遵循 PEP 8，使用 Ruff 進行檢查，Black 進行格式化。
- **語言規範**: 
  - UI 介面、錯誤訊息、文檔說明使用**繁體中文**。
  - 變數名稱、函數名稱、程式邏輯註解使用**英文**。
- **配置化**: 盡量避免硬編碼，應將解析邏輯與 Prompt 模板放入 `skills/` 配置中。

## 關鍵檔案參考
- `backend/app/main.py`: API 入口與 Lifespan 管理。
- `backend/app/services/pdf_parser.py`: Gemini AI 解析核心邏輯。
- `backend/app/services/image_matcher_deterministic.py`: 圖片匹配演算法。
- `frontend/app.py`: 前端單一入口邏輯。
- `skills/vendors/habitus.yaml`: 目前 POC 使用的供應商解析配置。

## 注意事項
- 系統目前為 POC (Proof of Concept) 階段，狀態儲存於記憶體中，重啟後端會導致資料丟失。
- 圖片提取與匹配依賴於 PDF 的頁面結構，若供應商格式大幅變動，需更新 `skills/` 中的配置。
