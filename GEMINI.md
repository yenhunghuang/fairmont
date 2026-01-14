# 家具報價單自動化系統 (Gemini FF&E Quotation System)

## 專案概述
本專案是一個利用 Google Gemini AI 自動化處理家具報價單的系統。主要功能是將供應商提供的 BOQ (Bill of Quantities) PDF 檔案解析，並轉換成特定格式（惠而蒙 Fairmont 格式，共 15 欄）的 Excel 報價單。

### 核心流程
1. **上傳 PDF**: 使用者上傳家具規格書或數量總表。
2. **AI 解析**: 利用 `gemini-3-flash-preview` 模型提取品項編號、描述、尺寸、位置、材質等資訊。
3. **圖片匹配**: 使用**確定性演算法（頁面偏移）**自動匹配規格頁與其對應的產品圖片，確保圖片與品項 100% 正確關聯。
4. **合併與排序**: 自動將數量總表與規格明細合併，並根據特定規則（如面料跟隨家具）進行排序。
5. **導出 Excel**: 產出符合 15 欄位規範的 Excel 檔案，包含圖片嵌入。

## 技術棧
- **後端**: Python 3.11+, FastAPI, Pydantic, Uvicorn
- **前端**: Streamlit (採用簡化的 **Step-based 自動化流程**)
- **AI 模型**: Google Gemini 3.0 Flash Preview (`gemini-3-flash-preview`)
- **PDF 處理**: PyMuPDF (fitz)
- **資料儲存**: InMemoryStore (具備 1 小時 TTL 的記憶體緩存，無資料庫)
- **品質控管**: Pytest, Ruff (Linter), Black (Formatter)
- **可觀測性**: Langfuse (整合追蹤 AI 調用成本與質量)

## 快速開始

### 環境設定
在專案根目錄建立 `.env` 檔案：
```env
GEMINI_API_KEY=你的_GEMINI_API_KEY
GEMINI_MODEL=gemini-3-flash-preview
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
# 建議使用專用樣式啟動
streamlit run app.py
```
前端預設運行在 `http://localhost:8501`。

## 核心特性

### 1. Skills 配置化系統
系統採用「配置驅動解析」(Configuration-driven Parsing) 架構，透過 `skills/` 目錄下的 YAML 檔案定義不同供應商的解析行為：
- **Vendor Skills**: 定義特定供應商（如 Habitus）的 PDF 結構、Prompt 模板、頁面偏移規則及圖片過濾標準。
- **Output Formats**: 定義 Excel 的輸出欄位、表頭樣式。
- **Merge Rules**: 定義欄位合併策略（如：地點欄位使用逗號分隔）。

### 2. 確定性圖片匹配 (Deterministic Image Matching)
不依賴模糊的 AI 視覺識別，而是利用 PDF 頁面索引與品項 `source_page` 的精確偏移計算，實現高可靠性的圖片關聯。

### 3. Step-based 流暢體驗
前端流程優化為「上傳 -> 自動處理 -> 一鍵下載」，大幅降低用戶操作複雜度，處理時間縮短 50%。

## 目錄結構
- `backend/`: FastAPI 應用程式核心代碼。
  - `app/api/`: API 路由定義（上傳、解析、合併、導出）。
  - `app/services/`: 核心業務邏輯（Gemini 解析、Excel 生成、圖片匹配、品項標準化）。
  - `app/models/`: Pydantic 資料模型。
- `frontend/`: Streamlit 前端應用程式。
  - `app.py`: 單一入口點，包含 Step-based 頁面邏輯。
  - `styles.py`: 品牌視覺與 CSS 樣式定義。
- `skills/`: 基於 YAML 的配置系統。
- `specs/`: 詳細的功能規格、資料模型與開發任務書。
- `docs/`: 包含 `POC_IMPLEMENTATION_SUMMARY.md` (實施總結) 與 `POC_QUICK_REFERENCE.md` (快速參考)。

## 開發規範
- **測試驅動 (TDD)**: 新功能需附帶測試，目標覆蓋率 >= 80%。
- **代碼風格**: 遵循 PEP 8，使用 Ruff 進行檢查。
- **語言規範**: 
  - UI 介面、說明文檔使用**繁體中文**。
  - 程式碼邏輯、變數名稱使用**英文**。

## 注意事項
- 系統目前為 POC 階段，狀態儲存於記憶體中，後端重啟會清空資料。
- 圖片匹配依賴於 `skills/vendors/*.yaml` 中的 `page_offset` 設定。
