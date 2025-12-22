# Implementation Plan: 家具報價單系統

**Branch**: `001-furniture-quotation-system` | **Date**: 2025-12-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-furniture-quotation-system/spec.md`

## Summary

家具報價單自動化系統 - 使用者上傳 BOQ（Bill of Quantities）PDF 檔案，使用 Google Gemini AI 解析內容，自動產出**完全比照惠而蒙格式**的 Excel 報價單。輸出欄位嚴格遵循範本 `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`，共 15 欄，不包含額外追蹤欄位。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.100+, Streamlit 1.28+, Google Generative AI (Gemini 1.5 Flash), openpyxl, python-multipart, httpx
**Storage**: 檔案系統暫存 + 記憶體儲存（InMemoryStore with 1-hour TTL，無資料庫）
**Testing**: pytest with pytest-asyncio, pytest-cov (coverage >= 80%)
**Target Platform**: Windows/Linux server (本地開發)
**Project Type**: Web application (前後端分離：FastAPI backend + Streamlit frontend)
**Performance Goals**: API 回應時間 < 200ms (標準請求), PDF 解析 < 5 分鐘/檔案
**Constraints**: 單檔最大 50MB, 最多 5 個檔案同時上傳, 匿名使用無需登入
**Scale/Scope**: 單機部署, 10+ 併發使用者

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 狀態 | 說明 |
|------|------|------|
| I. 代碼品質 | ✅ 通過 | Type hints 必須, ruff+black 檢查, 公開 API 必須有 docstrings |
| II. 測試標準 | ✅ 通過 | 測試優先開發, 覆蓋率 >= 80%, 單元/整合/E2E 測試 |
| III. UX 一致性 | ✅ 通過 | 繁體中文錯誤訊息, 操作狀態顯示 |
| IV. 效能要求 | ✅ 通過 | API < 200ms, 併發支援 |
| V. 語言要求 | ✅ 通過 | 繁體中文用於規格/UI/錯誤訊息 |

## Project Structure

### Documentation (this feature)

```text
specs/001-furniture-quotation-system/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # API contracts
│   └── openapi.yaml
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Environment settings
│   ├── store.py          # InMemoryStore
│   ├── models/           # Pydantic models
│   │   ├── boq_item.py
│   │   ├── source_document.py
│   │   ├── quotation.py
│   │   ├── processing_task.py
│   │   └── extracted_image.py
│   ├── services/         # Business logic
│   │   ├── pdf_parser.py
│   │   ├── image_extractor.py
│   │   └── excel_generator.py
│   ├── api/
│   │   ├── routes/       # FastAPI routes
│   │   │   ├── upload.py
│   │   │   ├── parse.py
│   │   │   ├── export.py
│   │   │   ├── task.py
│   │   │   └── health.py
│   │   └── dependencies.py
│   └── utils/
│       ├── errors.py
│       ├── file_manager.py
│       └── validators.py
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

frontend/
├── app.py                # Streamlit main
├── services/
│   └── api_client.py     # Backend API client
├── components/           # Reusable UI components
└── pages/
    ├── upload.py
    └── preview.py
```

**Structure Decision**: Web application 架構，前後端分離。後端使用 FastAPI 處理 API，前端使用 Streamlit 提供可視化介面。

## Complexity Tracking

*無違規需要說明。*

---

## Excel 輸出格式規範

> **重要**：輸出欄位完全比照範本 `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`，不包含額外追蹤欄位。

### 惠而蒙格式 Excel 欄位定義（共 15 欄）

| 欄位 | Excel Column | 說明 | 資料來源 |
|------|--------------|------|----------|
| NO. | A | 序號 | 系統自動產生 |
| Item no. | B | 項目編號 | PDF 解析 |
| Description | C | 品名描述 | PDF 解析 |
| Photo | D | 圖片 | PDF 提取後以 **Base64 編碼**嵌入儲存格 |
| Dimension WxDxH (mm) | E | 尺寸規格 | PDF 解析 |
| Qty | F | 數量 | PDF 解析 / 平面圖核對 |
| UOM | G | 單位 | PDF 解析 |
| Unit Rate (USD) | H | 單價 | **留空** - 使用者手動填寫 |
| Amount (USD) | I | 金額 | **留空** - 使用者手動填寫 |
| Unit CBM | J | 單位材積 | PDF 解析（若有） |
| Total CBM | K | 總材積 | 可由公式計算 (Unit CBM × Qty) |
| Note | L | 備註 | PDF 解析 |
| Location | M | 位置 | PDF 解析 |
| Materials Used / Specs | N | 材料/規格 | PDF 解析 |
| Brand | O | 品牌 | PDF 解析（若有） |

### 圖片處理規範

- **格式**：使用 Base64 編碼嵌入 Excel
- **儲存方式**：資料模型中以 `photo_base64: str` 欄位儲存
- **Excel 嵌入**：使用 openpyxl 將 Base64 解碼後嵌入儲存格
- **尺寸**：自動調整儲存格高度以適應圖片

### 價格欄位處理規則

- **Unit Rate (H 欄)**: 留空，使用者自行填入
- **Amount (I 欄)**: 留空，使用者自行填入（或可設為公式 `=F*H`）
- **Unit CBM (J 欄)**: 從 PDF 解析（若有資料）
- **Total CBM (K 欄)**: 若 Unit CBM 有值，可設為公式 `=F*J`；否則留空

### 資料模型欄位對照

| BOQItem 欄位 | Excel 欄位 | 說明 |
|--------------|------------|------|
| `no` | A: NO. | 序號 |
| `item_no` | B: Item no. | 項目編號 |
| `description` | C: Description | 描述 |
| `photo_base64` | D: Photo | Base64 編碼圖片，嵌入儲存格 |
| `dimension` | E: Dimension | 尺寸 |
| `qty` | F: Qty | 數量 |
| `uom` | G: UOM | 單位 |
| *(留空)* | H: Unit Rate | 使用者填寫 |
| *(留空)* | I: Amount | 使用者填寫 |
| `unit_cbm` | J: Unit CBM | 單位材積 |
| *(公式或留空)* | K: Total CBM | 計算欄位 |
| `note` | L: Note | 備註 |
| `location` | M: Location | 位置 |
| `materials_specs` | N: Materials Used / Specs | 材料規格 |
| `brand` | O: Brand | 品牌 |

---

## 資料模型變更

### BOQItem 更新欄位

基於 Excel 範本分析，需更新以下欄位：

```python
class BOQItem(BaseModel):
    # 核心欄位（完全比照 Excel 範本 15 欄）
    no: int                                    # A: NO.
    item_no: str                               # B: Item no.
    description: str                           # C: Description
    photo_base64: Optional[str] = None         # D: Photo (Base64 編碼)
    dimension: Optional[str] = None            # E: Dimension WxDxH (mm)
    qty: Optional[float] = None                # F: Qty
    uom: Optional[str] = None                  # G: UOM
    # H: Unit Rate - 不儲存，留空
    # I: Amount - 不儲存，留空
    unit_cbm: Optional[float] = None           # J: Unit CBM
    # K: Total CBM - 計算欄位
    note: Optional[str] = None                 # L: Note
    location: Optional[str] = None             # M: Location
    materials_specs: Optional[str] = None      # N: Materials Used / Specs
    brand: Optional[str] = None                # O: Brand

    # 內部追蹤欄位（不輸出到 Excel）
    id: str                                    # UUID
    source_document_id: str                    # 來源文件 ID
    source_page: Optional[int] = None          # 來源頁碼
```

### 移除欄位

因使用者要求「不用額外追蹤欄位」，以下欄位在 Excel 輸出時不包含：

- `photo_path` → 改用 `photo_base64`
- `source_type`, `source_location` - 不需要
- `qty_verified`, `qty_source` - 不需要

---

## Implementation Phases

### Phase 1: 核心上傳解析流程 (P1 User Story 1)

1. PDF 上傳 API
2. Gemini AI BOQ 解析（提取所有 15 欄資料）
3. 圖片提取並轉換為 Base64
4. 基本前端上傳介面

### Phase 2: Excel 輸出 (P1 User Story 1)

1. 惠而蒙格式 Excel 產生器（15 欄）
2. Base64 圖片嵌入儲存格
3. 下載功能

### Phase 3: 多檔案支援 (P2 User Story 2)

1. 多檔案上傳
2. 資料合併

### Phase 4: 平面圖核對 (P2 User Story 3)

1. 平面圖解析
2. 數量核對與補充

---

## 待研究項目

1. ✅ Excel 範本欄位結構 - 已分析完成（15 欄）
2. ✅ 圖片處理方式 - 使用 Base64 編碼
3. openpyxl Base64 圖片嵌入實作細節
4. Gemini AI prompt 優化（提取 Brand, Unit CBM 欄位）
