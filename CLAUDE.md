# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

家具報價單自動化系統 - 上傳 BOQ（Bill of Quantities）PDF 檔案，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單（15 欄）。

**API 基礎路徑**: `/api/v1/`

## 常用開發指令

### 後端 (FastAPI)

```bash
cd backend
pip install -r requirements.txt
pip install -e ".[dev]"

# 啟動
uvicorn app.main:app --reload

# 測試
pytest                              # 所有測試（含覆蓋率）
pytest tests/unit/                  # 單元測試
pytest tests/integration/           # 整合測試
pytest tests/contract/              # 契約測試
pytest -k "test_specific_name"      # 特定測試
pytest -v --cov-report=term-missing # 覆蓋率報告

# 程式碼品質
ruff check . --fix && black .       # 檢查 + 格式化（行寬 100）
```

### 前端 (Streamlit)

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### 環境設定

在專案根目錄建立 `.env`（與 `CLAUDE.md` 同層）：
- `GEMINI_API_KEY`: Google Gemini API 金鑰（必要）
- `GEMINI_MODEL`: 模型名稱（預設 `gemini-2.0-flash-lite`）
- `SKILLS_DIR`: Skills 配置目錄（預設 `skills/`）

#### Langfuse 可觀測性（選用）

追蹤 LLM 呼叫的 Token 用量、延遲、錯誤：
- `LANGFUSE_ENABLED`: 啟用追蹤（預設 `false`）
- `LANGFUSE_PUBLIC_KEY`: Langfuse Public Key
- `LANGFUSE_SECRET_KEY`: Langfuse Secret Key
- `LANGFUSE_HOST`: Langfuse 伺服器（預設 `https://cloud.langfuse.com`）
- `LANGFUSE_RELEASE`: 版本標記（預設 `1.0.0`）

使用方式：
```python
from app.services.observability import get_observability, TraceMetadata

obs = get_observability()
with obs.trace_generation("boq_extraction", TraceMetadata(vendor_id="habitus")) as ctx:
    response = model.generate_content(prompt)
    ctx["response"] = response
    ctx["prompt"] = prompt
```

## 非協商性標準

- **測試優先**: 編寫測試 → 驗證失敗 → 實作 → 驗證通過
- **覆蓋率**: >= 80%（關鍵路徑 100%）
- **效能**: API < 200ms (p95)，PDF 解析 < 15 秒
- **語言**: 錯誤訊息、文件使用繁體中文；程式碼可用英文
- **Python 版本**: >= 3.11

## 架構概述

### 資料流程

```
上傳 PDF → PDFParserService (Gemini AI) → BOQItem 列表 + 圖片匹配 → Excel 產出
```

### 關鍵架構模式

1. **記憶體儲存** (`store.py`): `InMemoryStore` 單例 + TTL 快取（1 小時），無資料庫
2. **服務單例**: 透過 `get_*()` 工廠函式取得（如 `get_pdf_parser()`）
3. **依賴注入**: `dependencies.py` 提供 `StoreDep`、`FileManagerDep` 等
4. **錯誤處理**: `raise_error(ErrorCode.XXX, "訊息")` 拋出 API 錯誤
5. **Skills 架構**: YAML 配置取代硬編碼（供應商規則、輸出格式、合併規則）

### Skills 架構

```
skills/
├── vendors/habitus.yaml        # 供應商配置（解析 Prompt、圖片排除規則）
├── output-formats/fairmont.yaml # 輸出格式（15 欄定義、樣式、條款）
└── core/merge-rules.yaml       # 合併規則（角色偵測、欄位合併策略）
```

使用方式：
```python
from app.services.skill_loader import get_skill_loader
loader = get_skill_loader()
skill = loader.load_vendor("habitus")         # VendorSkill
```

**服務與 Skill 對應**：

| 服務 | 使用的 Skill | 用途 |
|------|-------------|------|
| `pdf_parser.py` | VendorSkill | Prompt 模板 |
| `excel_generator.py` | OutputFormatSkill | 欄位/樣式 |
| `merge_service.py` | MergeRulesSkill | 合併策略 |
| `document_role_detector.py` | MergeRulesSkill | 角色偵測關鍵字 |
| `image_matcher_deterministic.py` | VendorSkill | 圖片排除規則、頁面偏移配置 |

### 圖片匹配系統

確定性演算法（非 Vision API）：
- **演算法**: 頁面偏移匹配（第 N 頁項目 → 第 N+offset 頁圖片）
- **偏移配置**: 從 `skills/vendors/*.yaml` 讀取，支援文件類型級別配置
  - `furniture_specification`: offset=1（家具明細）
  - `fabric_specification`: offset=1（面料明細）
  - `quantity_summary`: offset=0（數量總表，無圖片匹配）
- **排除規則**: 從 `skills/vendors/*.yaml` 讀取（Logo、色票、工程圖過濾）
- **效能**: < 100ms/PDF
- **位置**: `services/image_matcher_deterministic.py`

```yaml
# skills/vendors/habitus.yaml 配置範例
image_extraction:
  page_offset:
    default: 1
    by_document_type:
      furniture_specification: 1
      fabric_specification: 1
      quantity_summary: 0
```

## 技術限制

- 無 Redis/資料庫，狀態存於記憶體（1 小時 TTL）
- 單檔最大 50MB，每次最多 5 個檔案
- 單次處理最大 200 頁 PDF
- Unit Rate (H欄)、Amount (I欄) 留空由使用者填寫
- 跨表合併：最多 1 個數量總表

## 關鍵模式

### Response DTO

```python
# 內部使用
BOQItem          # 完整資料模型，含追蹤欄位（source_type, qty_verified, merge_status 等）

# API 回傳
BOQItemResponse  # 15 欄位 DTO，隱藏內部欄位
# 轉換：BOQItemResponse.from_boq_item(item)
```

### 錯誤處理

```python
from app.utils.errors import raise_error, ErrorCode
raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在", status_code=404)
```

### 新增服務

```python
# services/my_service.py
class MyService:
    def __init__(self, skill_loader: SkillLoader):
        self.skill_loader = skill_loader

_my_service: MyService | None = None

def get_my_service() -> MyService:
    global _my_service
    if _my_service is None:
        _my_service = MyService(get_skill_loader())
    return _my_service
```

## 惠而蒙 Excel 格式

15 欄：NO. / Item no. / Description / Photo / Dimension / Qty / UOM / Unit Rate / Amount / Unit CBM / Total CBM / Note / Location / Materials / Brand

範例：`docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`
配置：`skills/output-formats/fairmont.yaml`

## API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/documents` | POST | 上傳 PDF |
| `/api/v1/documents/{id}/parse-result` | GET | 取得 BOQ 項目 |
| `/api/v1/quotations` | POST | 建立報價單 |
| `/api/v1/quotations/{id}/excel` | GET | 下載 Excel |
| `/api/v1/quotations/merge` | POST | 合併多文件 |
| `/api/v1/tasks/{id}` | GET | 查詢任務狀態 |

## 目錄結構

```
backend/
├── app/
│   ├── api/routes/     # API 端點（upload, parse, export, merge, task）
│   ├── models/         # Pydantic 資料模型
│   ├── services/       # 業務邏輯（pdf_parser, excel_generator, merge_service 等）
│   ├── utils/          # 工具類（errors, validators, file_manager）
│   └── store.py        # InMemoryStore 記憶體儲存
├── tests/
│   ├── unit/           # 單元測試
│   ├── integration/    # 整合測試
│   └── contract/       # API 契約測試
frontend/
├── pages/              # Streamlit 頁面（upload, preview）
├── components/         # UI 元件
└── services/           # API 客戶端
skills/                 # YAML 配置（取代硬編碼）
specs/                  # 規格文件
```

## 規格文件

- 功能規格：`specs/001-furniture-quotation-system/spec.md`
- 資料模型：`specs/001-furniture-quotation-system/data-model.md`
- OpenAPI：`specs/001-furniture-quotation-system/contracts/openapi.yaml`

## 測試標記

```bash
pytest -m unit           # 單元測試
pytest -m integration    # 整合測試
pytest -m contract       # 契約測試
pytest -m slow           # 慢速測試
```
