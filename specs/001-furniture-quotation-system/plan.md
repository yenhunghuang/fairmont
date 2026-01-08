# Implementation Plan: 家具報價單系統 - 跨表合併功能

**Branch**: `001-furniture-quotation-system` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-furniture-quotation-system/spec.md`
**更新重點**: User Story 2 跨表合併功能（數量總表 + 明細規格表）

## Summary

家具報價單自動化系統 - 使用者上傳「數量總表」PDF 與多份「明細規格表」PDF，系統根據檔名自動識別 PDF 角色，以 Item No. 為主鍵進行標準化匹配，將數量總表的 Qty 覆蓋至明細規格表項目，多份明細規格表則依上傳順序合併非空欄位，最終產出單一惠而蒙格式 Excel 報價單（共 15 欄）。

**核心變更**:
- 新增 PDF 角色識別（`quantity_summary` / `detail_spec`）
- 新增 Item No. 標準化服務
- 新增跨表合併服務
- 新增合併報告模型

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.100+, Streamlit 1.28+, Google Generative AI (Gemini), openpyxl, python-multipart, httpx, PyMuPDF (fitz)
**Storage**: 檔案系統暫存 + InMemoryStore（TTLCache, 1 小時 TTL，無資料庫）
**Testing**: pytest with pytest-asyncio, pytest-cov (coverage >= 80%)
**Target Platform**: Windows/Linux server (本地開發)
**Project Type**: Web application (前後端分離：FastAPI backend + Streamlit frontend)
**Performance Goals**:
- API 回應時間: < 200ms (p95)
- 單檔 PDF 解析: < 5 分鐘
- 多 PDF 跨表合併: < 10 分鐘（最大 200 頁）
**Constraints**:
- 單檔最大 50MB
- 每次上傳最多 5 個 PDF
- 總頁數上限 200 頁
- 僅允許 1 份數量總表
- 匿名使用，無需登入
**Scale/Scope**: 單機部署, 10+ 併發使用者, 單次合併最多約 1000 個 BOQ 項目

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 狀態 | 說明 |
|------|------|------|
| I. 代碼品質 | ✅ 通過 | Type hints 必須, ruff+black 檢查, 公開 API 必須有 docstrings |
| II. 測試標準 | ✅ 通過 | 測試優先開發, 覆蓋率 >= 80%, 單元/整合/契約測試 |
| III. UX 一致性 | ✅ 通過 | 繁體中文錯誤訊息, 載入狀態顯示, 合併進度回報 |
| IV. 效能要求 | ✅ 通過 | API < 200ms, 單檔 < 5 分鐘, 多檔 < 10 分鐘 |
| V. 語言要求 | ✅ 通過 | 繁體中文用於規格/UI/錯誤訊息 |

**Constitution Gate: PASSED**

## Project Structure

### Documentation (this feature)

```text
specs/001-furniture-quotation-system/
├── spec.md              # 功能規格（已更新跨表合併需求）
├── plan.md              # 本文件
├── research.md          # Phase 0 研究產出
├── data-model.md        # Phase 1 資料模型
├── quickstart.md        # Phase 1 快速開始指南
├── contracts/           # Phase 1 API 契約
│   └── openapi.yaml
└── tasks.md             # Phase 2 任務清單 (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                      # FastAPI 應用入口
│   ├── config.py                    # Pydantic Settings
│   ├── store.py                     # InMemoryStore 單例
│   ├── models/
│   │   ├── boq_item.py             # BOQ 項目模型 (23 欄位)
│   │   ├── source_document.py      # 來源文件模型 [修改: 新增 document_role]
│   │   ├── quotation.py            # 報價單模型
│   │   ├── processing_task.py      # 背景任務模型
│   │   ├── extracted_image.py      # 圖片元數據
│   │   ├── responses.py            # API DTO [修改: 新增 MergeReportResponse]
│   │   └── merge_report.py         # [新增] 合併報告模型
│   ├── services/
│   │   ├── pdf_parser.py           # PDF 解析 + Gemini AI
│   │   ├── quantity_parser.py      # [新增] 數量總表專用解析
│   │   ├── item_normalizer.py      # [新增] Item No. 標準化
│   │   ├── merge_service.py        # [新增] 跨表合併服務
│   │   ├── image_selector.py       # [新增] 圖片解析度選擇
│   │   ├── document_role_detector.py  # [新增] PDF 角色偵測
│   │   ├── image_extractor.py      # PDF 圖片提取
│   │   ├── image_matcher_deterministic.py  # 確定性圖片匹配
│   │   ├── excel_generator.py      # Excel 產生
│   │   └── quotation_format.py     # 共用格式定義
│   ├── api/
│   │   ├── dependencies.py         # 依賴注入
│   │   └── routes/
│   │       ├── upload.py           # [修改] 上傳端點 (擴充角色識別回傳)
│   │       ├── parse.py            # 解析端點
│   │       ├── export.py           # 匯出端點
│   │       ├── merge.py            # [新增] 合併端點
│   │       ├── task.py             # 任務狀態端點
│   │       └── health.py           # 健康檢查
│   └── utils/
│       ├── errors.py               # [修改] 新增 MERGE_* 錯誤碼
│       └── file_manager.py         # 檔案管理
└── tests/
    ├── conftest.py                  # [修改] 新增合併相關 fixtures
    ├── unit/
    │   ├── test_quantity_parser.py       # [新增]
    │   ├── test_item_normalizer.py       # [新增]
    │   ├── test_merge_service.py         # [新增]
    │   ├── test_image_selector.py        # [新增]
    │   ├── test_document_role_detector.py # [新增]
    │   └── ... (現有測試)
    ├── integration/
    │   ├── test_merge_flow.py            # [新增]
    │   └── ... (現有測試)
    └── contract/
        ├── test_merge_api.py             # [新增]
        └── ... (現有測試)

frontend/
├── app.py                           # [修改] Streamlit 主程式 (擴充合併流程)
├── services/api_client.py          # [修改] API 客戶端 (新增合併方法)
├── components/
│   ├── file_uploader.py            # [修改] 擴充顯示 PDF 角色
│   ├── merge_progress.py           # [新增] 合併進度顯示
│   └── merge_report.py             # [新增] 合併報告元件
└── pages/
    └── merge_preview.py            # [新增] 合併預覽頁面
```

**Structure Decision**: 遵循現有 Web application 架構，新增服務於 `services/`，新增路由於 `routes/`，保持現有模式。

## Complexity Tracking

> **無違規需要說明**

---

## Phase 0: Research Summary

### R-001: PDF 角色自動識別策略

**Decision**: 檔名關鍵字匹配（大小寫不敏感）
**Rationale**:
- 關鍵字清單: `["Qty", "Overall", "Summary", "數量", "總量"]`
- 符合任一關鍵字 → `quantity_summary`
- 否則 → `detail_spec`
- 簡單、快速、可預測
**Alternatives considered**:
- 內容分析（需額外 AI 呼叫，增加成本與延遲）→ 拒絕
- 使用者手動選擇（增加操作複雜度）→ 作為覆寫機制保留

### R-002: Item No. 標準化演算法

**Decision**: 正規表達式清理 + 大小寫統一
**Implementation**:
```python
import re

def normalize_item_no(item_no: str) -> str:
    """標準化 Item No. 以便跨 PDF 匹配."""
    # 1. 移除前後空白
    normalized = item_no.strip()
    # 2. 統一大寫
    normalized = normalized.upper()
    # 3. 移除內部空格
    normalized = re.sub(r'\s+', '', normalized)
    # 4. 統一分隔符號 (. 和 - 視為相同，統一為 -)
    normalized = re.sub(r'[.\-]+', '-', normalized)
    return normalized
```
**Examples**:
- `"DLX-100"` → `"DLX-100"`
- `"DLX 100"` → `"DLX100"` → `"DLX-100"` (經標準化)
- `"dlx.100"` → `"DLX-100"`
**Alternatives considered**:
- 僅移除空格（無法處理 `"DLX.100"` vs `"DLX-100"`）→ 拒絕
- 模糊匹配（複雜度高，可能產生誤配）→ 拒絕

### R-003: 數量總表解析策略

**Decision**: 專用 Gemini prompt + 結構化 JSON 輸出
**Rationale**:
- 數量總表格式簡單（CODE + TOTAL QTY 兩欄）
- 與明細規格表使用不同 prompt 提高準確率
- 輸出格式:
```json
[
  {"item_no": "DLX-100", "qty": 239.0},
  {"item_no": "DLX-101", "qty": 248.0}
]
```
**Prompt 要點**:
- 僅提取 CODE/Item No. 與 TOTAL QTY 兩個欄位
- 忽略表頭、小計、合計列
- 數量使用浮點數（處理 `1,234.00` 格式）

### R-004: 多來源欄位合併策略

**Decision**: 上傳順序優先 + 非空覆蓋
**Rules**:
1. 先上傳的 PDF 非空欄位優先
2. 若先上傳為空、後上傳有值，則取後上傳值
3. **圖片特例**：選擇解析度較高者（像素總數 `width × height`）
4. **數量總表 Qty 最高優先**：無條件覆蓋明細規格表數量

**Implementation**:
```python
MERGEABLE_FIELDS = [
    "description", "dimension", "uom", "unit_cbm",
    "note", "location", "materials_specs", "brand"
]

def merge_items(items: List[BOQItem], qty_from_summary: Optional[float]) -> BOQItem:
    """合併多個 BOQItem 為單一項目."""
    merged = items[0].model_copy()

    # 合併非空欄位
    for item in items[1:]:
        for field in MERGEABLE_FIELDS:
            if getattr(merged, field) is None and getattr(item, field) is not None:
                setattr(merged, field, getattr(item, field))

    # 圖片選擇最高解析度
    merged.photo_base64 = select_highest_resolution_image(items)

    # 數量總表覆蓋
    if qty_from_summary is not None:
        merged.qty = qty_from_summary
        merged.qty_source = "quantity_summary"
        merged.qty_verified = True

    return merged
```

### R-005: 合併報告結構

**Decision**: 結構化 JSON 報告
**Schema**:
```python
class MergeReport(BaseModel):
    """跨 PDF 合併報告."""
    total_items: int                          # 合併後項目總數
    matched_items: int                        # 成功匹配項目數
    unmatched_in_quantity_summary: List[str]  # 僅在數量總表的 Item No.
    unmatched_in_detail_spec: List[str]       # 僅在明細規格表的 Item No.
    qty_not_verified: List[str]               # 數量未驗證的 Item No.
    format_warnings: List[FormatWarning]      # Item No. 格式差異警告

class FormatWarning(BaseModel):
    original: str      # 原始 Item No.
    normalized: str    # 標準化後
    source_file: str   # 來源檔案
```

### R-006: 現有服務重用策略

**Decision**: 最大化重用現有服務
**重用清單**:
| 現有服務 | 用途 | 修改需求 |
|---------|------|---------|
| `PDFParserService` | 明細規格表解析 | 無需修改 |
| `ImageExtractorService` | 圖片提取 | 無需修改 |
| `ImageMatcherDeterministic` | 圖片匹配 | 無需修改 |
| `ExcelGeneratorService` | Excel 產生 | 無需修改 |
| `InMemoryStore` | 資料儲存 | 新增 merge_report 快取 |
| `ProcessingTask` | 背景任務 | 新增 `merge` 任務類型 |

**新增服務**:
| 新服務 | 職責 |
|-------|------|
| `DocumentRoleDetector` | PDF 角色偵測 |
| `ItemNormalizer` | Item No. 標準化 |
| `QuantityParser` | 數量總表解析 |
| `MergeService` | 跨表合併邏輯 |
| `ImageSelector` | 圖片解析度選擇 |

---

## Phase 1: Design Artifacts

### 資料模型變更

#### SourceDocument 修改

```python
# backend/app/models/source_document.py
from typing import Literal

DocumentRole = Literal["quantity_summary", "detail_spec", "floor_plan", "unknown"]

class SourceDocument(BaseModel):
    # ... 現有欄位 ...

    # [新增] PDF 角色
    document_role: DocumentRole = "unknown"
    document_role_auto_detected: bool = True  # 是否為自動偵測
```

#### MergeReport 新增

```python
# backend/app/models/merge_report.py
from pydantic import BaseModel
from typing import List
from datetime import datetime

class FormatWarning(BaseModel):
    """Item No. 格式差異警告."""
    original: str
    normalized: str
    source_file: str

class MergeReport(BaseModel):
    """跨 PDF 合併報告."""
    id: str
    quotation_id: str
    created_at: datetime

    # 統計資訊
    total_items: int
    matched_items: int
    match_rate: float  # matched_items / total_items

    # 未匹配項目
    unmatched_in_quantity_summary: List[str]
    unmatched_in_detail_spec: List[str]
    qty_not_verified: List[str]

    # 警告
    format_warnings: List[FormatWarning]

    # 來源檔案
    quantity_summary_file: Optional[str]
    detail_spec_files: List[str]
```

#### BOQItem 修改

```python
# backend/app/models/boq_item.py
# 新增欄位
source_files: List[str] = []  # 來源檔案清單（合併時記錄）
```

### API 端點變更

#### 新增 Merge API

```yaml
# POST /api/v1/quotations/merge
# 從多個文件建立合併報價單

Request:
  document_ids: List[str]  # 要合併的文件 ID 清單

Response (202 Accepted):
  task_id: str
  message: str

# GET /api/v1/quotations/{id}/merge-report
# 取得合併報告

Response (200 OK):
  MergeReport
```

#### Upload API 修改

```yaml
# POST /api/v1/documents
# Response 新增欄位

Response:
  # ... 現有欄位 ...
  document_role: str          # "quantity_summary" | "detail_spec" | "unknown"
  document_role_auto_detected: bool
```

### 錯誤碼新增

```python
# backend/app/utils/errors.py
class ErrorCode(str, Enum):
    # ... 現有錯誤碼 ...

    # 合併相關
    MERGE_MULTIPLE_QUANTITY_SUMMARY = "MERGE_001"  # 上傳多份數量總表
    MERGE_NO_DETAIL_SPEC = "MERGE_002"             # 無明細規格表
    MERGE_ITEM_NOT_FOUND = "MERGE_003"             # Item No. 未找到
    MERGE_FAILED = "MERGE_004"                     # 合併失敗

ERROR_MESSAGES = {
    # ... 現有訊息 ...
    ErrorCode.MERGE_MULTIPLE_QUANTITY_SUMMARY: "上傳多份數量總表，請僅保留一份",
    ErrorCode.MERGE_NO_DETAIL_SPEC: "未上傳明細規格表，無法進行合併",
    ErrorCode.MERGE_ITEM_NOT_FOUND: "Item No. 在明細規格表中未找到",
    ErrorCode.MERGE_FAILED: "合併處理失敗",
}
```

---

## Implementation Phases

### Phase 1: PDF 角色識別（已完成現有解析基礎上擴充）

1. ✅ PDF 上傳 API（現有）
2. ✅ Gemini AI BOQ 解析（現有）
3. ✅ 圖片提取（現有）
4. [新增] DocumentRoleDetector 服務
5. [修改] Upload API 回傳 document_role

### Phase 2: 數量總表解析

1. [新增] QuantityParser 服務
2. [新增] 專用 Gemini prompt
3. [新增] 單元測試

### Phase 3: Item No. 標準化

1. [新增] ItemNormalizer 服務
2. [新增] 單元測試（涵蓋各種格式）

### Phase 4: 跨表合併核心

1. [新增] MergeService 服務
2. [新增] ImageSelector（解析度選擇）
3. [新增] MergeReport 模型
4. [新增] 整合測試

### Phase 5: API 與前端

1. [新增] POST /quotations/merge 端點
2. [新增] GET /quotations/{id}/merge-report 端點
3. [修改] 前端合併流程 UI
4. [新增] 合併報告顯示元件
5. [新增] 契約測試

---

## Excel 輸出格式規範

> **重要**：輸出欄位完全比照範本 `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`，不包含額外追蹤欄位。

### 惠而蒙格式 Excel 欄位定義（共 15 欄）

| 欄位 | Excel Column | 說明 | 資料來源 |
|------|--------------|------|----------|
| NO. | A | 序號 | 系統自動產生 |
| Item no. | B | 項目編號 | PDF 解析 |
| Description | C | 品名描述 | PDF 解析（合併優先） |
| Photo | D | 圖片 | PDF 提取（選擇最高解析度） |
| Dimension WxDxH (mm) | E | 尺寸規格 | PDF 解析（合併優先） |
| Qty | F | 數量 | **數量總表優先** / 明細規格表 |
| UOM | G | 單位 | PDF 解析 |
| Unit Rate (USD) | H | 單價 | **留空** |
| Amount (USD) | I | 金額 | **留空** |
| Unit CBM | J | 單位材積 | PDF 解析 |
| Total CBM | K | 總材積 | 公式 `=F*J` |
| Note | L | 備註 | PDF 解析 |
| Location | M | 位置 | PDF 解析 |
| Materials Used / Specs | N | 材料/規格 | PDF 解析（合併優先） |
| Brand | O | 品牌 | PDF 解析 |

---

## Out of Scope（本次不實作）

- Google Sheets 匯出功能
- 用戶編輯 BOQ 項目
- 歷史記錄與版本管理
- 多語系支援

---

*Plan generated by `/speckit.plan` command - 2025-12-23*
