# Data Model: 家具報價單系統

**Feature Branch**: `001-furniture-quotation-system`
**Date**: 2025-12-19
**Updated**: 2025-12-23 - 新增跨表合併相關模型
**Spec Reference**: [spec.md](./spec.md)

## 概述

本文件定義家具報價單系統的資料模型，包含核心實體、欄位定義、驗證規則及狀態轉換。由於系統不使用資料庫（使用檔案系統暫存），資料模型主要以 Pydantic models 形式實作。

---

## 核心實體

### 1. BOQItem（BOQ 項目）

代表一筆從 PDF 解析出的家具或物料資料。

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime

class BOQItem(BaseModel):
    """BOQ 項目資料模型（完全比照惠而蒙格式 15 欄）"""

    # 主鍵（系統產生，內部使用）
    id: str = Field(..., description="唯一識別碼 (UUID)")

    # Excel 欄位（完全比照範本 15 欄）
    no: int = Field(..., ge=1, description="A: 序號 (NO.)")
    item_no: str = Field(..., description="B: 項目編號 (Item no.)")
    description: str = Field(..., description="C: 描述 (Description)")
    photo_base64: Optional[str] = Field(None, description="D: 圖片 Base64 編碼 (Photo)")
    dimension: Optional[str] = Field(None, description="E: 尺寸規格 WxDxH mm (Dimension)")
    qty: Optional[float] = Field(None, ge=0, description="F: 數量 (Qty)")
    uom: Optional[str] = Field(None, description="G: 單位 (UOM)，如：ea, m, set")
    # H: Unit Rate - 不儲存，留空由使用者填寫
    # I: Amount - 不儲存，留空由使用者填寫
    unit_cbm: Optional[float] = Field(None, ge=0, description="J: 單位材積 (Unit CBM)")
    # K: Total CBM - 公式計算 =F*J
    note: Optional[str] = Field(None, description="L: 備註 (Note)")
    location: Optional[str] = Field(None, description="M: 位置/區域 (Location)")
    materials_specs: Optional[str] = Field(None, description="N: 材料/規格 (Materials Used / Specs)")
    brand: Optional[str] = Field(None, description="O: 品牌 (Brand)")

    # 內部追蹤欄位（不輸出到 Excel）
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")

    @field_validator("item_no")
    @classmethod
    def validate_item_no(cls, v: str) -> str:
        """驗證項次編號不為空"""
        if not v or not v.strip():
            raise ValueError("項次編號不可為空")
        return v.strip()

    @field_validator("qty")
    @classmethod
    def validate_qty(cls, v: Optional[float]) -> Optional[float]:
        """驗證數量為正數"""
        if v is not None and v < 0:
            raise ValueError("數量不可為負數")
        return v
```

#### 欄位說明

| 欄位 | 類型 | 必填 | Excel 欄位 | 說明 | 驗證規則 |
|------|------|------|------------|------|----------|
| id | string | ✅ | *(內部)* | UUID 格式唯一識別碼 | 系統自動產生 |
| no | int | ✅ | A: NO. | 序號 | ≥ 1，系統產生 |
| item_no | string | ✅ | B: Item no. | 項目編號 | 不可為空 |
| description | string | ✅ | C: Description | 描述 | 不可為空 |
| photo_base64 | string | ❌ | D: Photo | Base64 編碼圖片 | - |
| dimension | string | ❌ | E: Dimension | 尺寸規格 WxDxH mm | - |
| qty | float | ❌ | F: Qty | 數量 | ≥ 0 |
| uom | string | ❌ | G: UOM | 單位，如：ea, m, set | - |
| *(不儲存)* | - | - | H: Unit Rate | 單價 | **使用者填寫** |
| *(不儲存)* | - | - | I: Amount | 金額 | **使用者填寫** |
| unit_cbm | float | ❌ | J: Unit CBM | 單位材積 | ≥ 0 |
| *(公式)* | - | - | K: Total CBM | 總材積 | `=F*J` |
| note | string | ❌ | L: Note | 備註 | - |
| location | string | ❌ | M: Location | 位置/區域 | - |
| materials_specs | string | ❌ | N: Materials Used / Specs | 材料/規格 | - |
| brand | string | ❌ | O: Brand | 品牌 | - |
| source_document_id | string | ✅ | *(內部)* | 來源文件 ID | 有效 UUID |
| source_page | int | ❌ | *(內部)* | 來源頁碼 | ≥ 1 |

---

### 2. SourceDocument（來源文件）

代表使用者上傳的 PDF 檔案。

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime

class SourceDocument(BaseModel):
    """來源文件資料模型"""

    id: str = Field(..., description="唯一識別碼 (UUID)")

    # 檔案資訊
    filename: str = Field(..., description="原始檔名")
    file_path: str = Field(..., description="暫存檔案路徑")
    file_size: int = Field(..., ge=0, le=52428800, description="檔案大小（bytes，最大 50MB）")
    mime_type: str = Field("application/pdf", description="MIME 類型")

    # 文件類型
    document_type: Literal["boq", "floor_plan", "unknown"] = Field(
        "unknown", description="文件類型"
    )

    # 解析狀態
    parse_status: Literal["pending", "processing", "completed", "failed"] = Field(
        "pending", description="解析狀態"
    )
    parse_progress: int = Field(0, ge=0, le=100, description="解析進度 %")
    parse_message: Optional[str] = Field(None, description="解析狀態訊息")
    parse_error: Optional[str] = Field(None, description="解析錯誤訊息")

    # 解析結果
    total_pages: Optional[int] = Field(None, ge=1, description="總頁數")
    extracted_items_count: int = Field(0, ge=0, description="提取的項目數")
    extracted_images_count: int = Field(0, ge=0, description="提取的圖片數")

    # 時間戳記
    uploaded_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = Field(None, description="處理完成時間")

    # Gemini API 相關
    gemini_file_uri: Optional[str] = Field(None, description="Gemini File API URI")
```

#### 狀態轉換圖

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌─────────┐     ┌─────────────┐     ┌───────────┐     ┌──┴────┐
│ pending │────▶│ processing  │────▶│ completed │     │ failed│
└─────────┘     └─────────────┘     └───────────┘     └───────┘
    │                 │                                   ▲
    │                 └───────────────────────────────────┘
    │                         (解析失敗)
    └─────────────────────────────────────────────────────┘
                    (檔案驗證失敗)
```

---

### 3. Quotation（報價單）

代表產出的報價單，包含多個 BOQ 項目。

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class Quotation(BaseModel):
    """報價單資料模型"""

    id: str = Field(..., description="唯一識別碼 (UUID)")

    # 基本資訊
    title: Optional[str] = Field(None, description="報價單標題")
    created_at: datetime = Field(default_factory=datetime.now)

    # 來源文件
    source_document_ids: List[str] = Field(
        default_factory=list, description="來源文件 ID 列表"
    )

    # 包含的項目
    items: List[BOQItem] = Field(default_factory=list, description="BOQ 項目列表")

    # 統計資訊
    total_items: int = Field(0, ge=0, description="總項目數")
    items_with_qty: int = Field(0, ge=0, description="有數量的項目數")
    items_with_photo: int = Field(0, ge=0, description="有圖片的項目數")
    items_from_floor_plan: int = Field(0, ge=0, description="從平面圖補充數量的項目數")

    # 匯出狀態
    export_status: Literal["pending", "generating", "completed", "failed"] = Field(
        "pending", description="匯出狀態"
    )
    export_path: Optional[str] = Field(None, description="Excel 檔案路徑")
    export_error: Optional[str] = Field(None, description="匯出錯誤訊息")

    def update_statistics(self):
        """更新統計資訊"""
        self.total_items = len(self.items)
        self.items_with_qty = sum(1 for item in self.items if item.qty is not None)
        self.items_with_photo = sum(1 for item in self.items if item.photo_base64)
        self.items_from_floor_plan = sum(
            1 for item in self.items if item.qty_source == "floor_plan"
        )
```

---

### 4. ProcessingTask（處理任務）

追蹤長時間處理任務的狀態。

```python
from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime

class ProcessingTask(BaseModel):
    """處理任務狀態模型"""

    task_id: str = Field(..., description="任務 ID (UUID)")

    # 任務類型
    task_type: Literal["parse_pdf", "extract_images", "generate_excel", "analyze_floor_plan"] = Field(
        ..., description="任務類型"
    )

    # 狀態
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        "pending", description="任務狀態"
    )
    progress: int = Field(0, ge=0, le=100, description="進度百分比")
    message: str = Field("等待處理", description="狀態訊息（繁體中文）")

    # 結果
    result: Optional[Any] = Field(None, description="任務結果")
    error: Optional[str] = Field(None, description="錯誤訊息")

    # 時間戳記
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(None, description="開始時間")
    completed_at: Optional[datetime] = Field(None, description="完成時間")

    # 關聯
    document_id: Optional[str] = Field(None, description="相關文件 ID")
    quotation_id: Optional[str] = Field(None, description="相關報價單 ID")

    def start(self):
        """標記任務開始"""
        self.status = "processing"
        self.started_at = datetime.now()

    def complete(self, result: Any = None):
        """標記任務完成"""
        self.status = "completed"
        self.progress = 100
        self.message = "處理完成"
        self.result = result
        self.completed_at = datetime.now()

    def fail(self, error: str):
        """標記任務失敗"""
        self.status = "failed"
        self.error = error
        self.message = f"處理失敗：{error}"
        self.completed_at = datetime.now()

    def update_progress(self, progress: int, message: str):
        """更新進度"""
        self.progress = min(max(progress, 0), 100)
        self.message = message
```

---

### 5. ExtractedImage（提取的圖片）

代表從 PDF 提取的圖片資訊。

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ExtractedImage(BaseModel):
    """提取圖片資料模型"""

    id: str = Field(..., description="唯一識別碼 (UUID)")

    # 檔案資訊
    filename: str = Field(..., description="圖片檔名")
    file_path: str = Field(..., description="圖片檔案路徑")
    format: str = Field(..., description="圖片格式（png/jpeg/etc）")

    # 尺寸
    width: int = Field(..., ge=1, description="寬度 (px)")
    height: int = Field(..., ge=1, description="高度 (px)")
    file_size: int = Field(..., ge=0, description="檔案大小 (bytes)")

    # 來源
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: int = Field(..., ge=1, description="來源頁碼")

    # 關聯
    boq_item_id: Optional[str] = Field(None, description="關聯的 BOQ 項目 ID")
    matched: bool = Field(False, description="是否已配對到 BOQ 項目")

    # 時間戳記
    extracted_at: datetime = Field(default_factory=datetime.now)
```

---

## 資料關聯圖

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Quotation                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  id, title, created_at                                          │    │
│  │  source_document_ids[]                                          │    │
│  │  items[]  ──────────────────────────────────────────┐           │    │
│  │  statistics                                          │           │    │
│  └─────────────────────────────────────────────────────│───────────┘    │
└─────────────────────────────────────────────────────────│────────────────┘
                                                          │
                                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BOQItem                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  id, item_no, description                                       │    │
│  │  photo_base64 ──────────────────────────────────┐               │    │
│  │  dimension, qty, uom, location, materials_specs  │               │    │
│  │  source_document_id ────────────────────────────│───┐           │    │
│  │  source_type, source_page, source_location       │   │           │    │
│  │  qty_verified, qty_source                        │   │           │    │
│  └─────────────────────────────────────────────────│───│───────────┘    │
└─────────────────────────────────────────────────────│───│────────────────┘
                                                      │   │
                      ┌───────────────────────────────┘   │
                      ▼                                   │
┌────────────────────────────────────┐                   │
│        ExtractedImage              │                   │
│  ┌──────────────────────────────┐  │                   │
│  │  id, filename, file_path     │  │                   │
│  │  format, width, height       │  │                   │
│  │  source_document_id ─────────│──│───────────────────┤
│  │  source_page                 │  │                   │
│  │  boq_item_id (back ref)      │  │                   │
│  └──────────────────────────────┘  │                   │
└────────────────────────────────────┘                   │
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           SourceDocument                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  id, filename, file_path, file_size                             │    │
│  │  document_type (boq/floor_plan)                                 │    │
│  │  parse_status, parse_progress, parse_message                    │    │
│  │  total_pages, extracted_items_count, extracted_images_count     │    │
│  │  gemini_file_uri                                                │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          ProcessingTask                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  task_id, task_type, status, progress, message                  │    │
│  │  result, error                                                  │    │
│  │  document_id ──────────────────────────▶ SourceDocument         │    │
│  │  quotation_id ─────────────────────────▶ Quotation              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 惠而蒙格式欄位對照

> 參考範例：`docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`
> **完全比照範本 15 欄**，不包含額外追蹤欄位

| Excel 欄位 | 資料模型欄位 | 說明 | 資料來源 |
|------------|--------------|------|----------|
| A: NO. | `BOQItem.no` | 序號 | 系統產生 |
| B: Item no. | `BOQItem.item_no` | 項目編號 | PDF 解析 |
| C: Description | `BOQItem.description` | 描述 | PDF 解析 |
| D: Photo | `BOQItem.photo_base64` | 圖片（Base64 編碼嵌入儲存格） | PDF 提取 |
| E: Dimension WxDxH (mm) | `BOQItem.dimension` | 尺寸規格 | PDF 解析 |
| F: Qty | `BOQItem.qty` | 數量 | PDF 解析 |
| G: UOM | `BOQItem.uom` | 單位 | PDF 解析 |
| H: Unit Rate (USD) | *(留空)* | 單價 | **使用者填寫** |
| I: Amount (USD) | *(留空)* | 金額 | **使用者填寫** |
| J: Unit CBM | `BOQItem.unit_cbm` | 單位材積 | PDF 解析（若有） |
| K: Total CBM | *(公式 =F*J)* | 總材積 | 計算欄位 |
| L: Note | `BOQItem.note` | 備註 | PDF 解析 |
| M: Location | `BOQItem.location` | 位置 | PDF 解析 |
| N: Materials Used / Specs | `BOQItem.materials_specs` | 材料/規格 | PDF 解析 |
| O: Brand | `BOQItem.brand` | 品牌 | PDF 解析（若有） |

---

## 驗證規則總覽

### BOQItem
| 規則 | 描述 |
|------|------|
| VR-001 | `item_no` 必填，不可為空白 |
| VR-002 | `description` 必填，不可為空白 |
| VR-003 | `qty` 若有值，必須 ≥ 0 |
| VR-004 | `source_type` 必須為 `boq`/`floor_plan`/`manual` |
| VR-005 | `source_page` 若有值，必須 ≥ 1 |

### SourceDocument
| 規則 | 描述 |
|------|------|
| VR-006 | `file_size` 必須 ≤ 50MB (52,428,800 bytes) |
| VR-007 | `filename` 必須以 `.pdf` 結尾（不區分大小寫） |
| VR-008 | `parse_progress` 必須在 0-100 範圍內 |

### ProcessingTask
| 規則 | 描述 |
|------|------|
| VR-009 | `progress` 必須在 0-100 範圍內 |
| VR-010 | `status` 變更必須遵循狀態轉換圖 |

---

## 跨表合併相關模型 (2025-12-23 新增)

### 6. DocumentRole（文件角色）

定義 PDF 文件在跨表合併中的角色。

```python
from enum import Enum

class DocumentRole(str, Enum):
    """PDF 文件角色"""
    QUANTITY_SUMMARY = "quantity_summary"  # 數量總表
    DETAIL_SPEC = "detail_spec"            # 明細規格表
    UNKNOWN = "unknown"                     # 未知（需手動指定）
```

#### 角色偵測關鍵字

| 角色 | 檔名關鍵字（不區分大小寫） |
|------|---------------------------|
| `quantity_summary` | `qty`, `overall`, `summary`, `數量`, `總量`, `總表` |
| `detail_spec` | 其他所有 PDF |

---

### 7. QuantitySummaryItem（數量總表項目）

代表從數量總表 PDF 解析出的數量資料。

```python
from pydantic import BaseModel, Field
from typing import Optional

class QuantitySummaryItem(BaseModel):
    """數量總表項目 - 僅包含 Item No 與數量"""

    # 項目識別
    item_no_raw: str = Field(..., description="原始 Item No.（從 PDF 解析）")
    item_no_normalized: str = Field(..., description="標準化後的 Item No.")

    # 數量資訊
    total_qty: float = Field(..., ge=0, description="總數量")
    uom: Optional[str] = Field(None, description="單位")

    # 來源追蹤
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")

    @classmethod
    def normalize_item_no(cls, item_no: str) -> str:
        """
        標準化 Item No. 以支援跨表比對

        規則：
        1. 去除前後空白
        2. 轉為大寫
        3. 移除所有空格
        4. 統一分隔符號為 '-'
        """
        import re
        normalized = item_no.strip()
        normalized = normalized.upper()
        normalized = re.sub(r'\s+', '', normalized)
        normalized = re.sub(r'[.\-_]+', '-', normalized)
        return normalized
```

---

### 8. MergeResult（合併結果）

記錄單一項目的合併結果與來源追蹤。

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum

class MergeStatus(str, Enum):
    """合併狀態"""
    MATCHED = "matched"           # 成功配對（數量總表有對應項目）
    UNMATCHED = "unmatched"       # 未配對（數量總表無對應項目）
    QUANTITY_ONLY = "quantity_only"  # 僅在數量總表出現

class MergeResult(BaseModel):
    """單一項目的合併結果"""

    # 項目識別
    item_no_normalized: str = Field(..., description="標準化後的 Item No.")
    original_item_nos: List[str] = Field(default_factory=list, description="原始 Item No. 列表")

    # 合併狀態
    status: MergeStatus = Field(..., description="合併狀態")

    # 來源追蹤
    quantity_source: Optional[str] = Field(None, description="數量來源文件 ID")
    detail_sources: List[str] = Field(default_factory=list, description="明細來源文件 ID 列表（按上傳順序）")

    # 欄位來源對照（用於 Merge Report 顯示）
    field_sources: Dict[str, str] = Field(
        default_factory=dict,
        description="欄位 -> 來源文件 ID 對照"
    )

    # 圖片選擇
    selected_image_source: Optional[str] = Field(None, description="選用圖片的來源文件 ID")
    image_resolution: Optional[int] = Field(None, description="選用圖片的解析度 (width × height)")
```

---

### 9. MergeReport（合併報告）

完整的跨表合併報告，提供給使用者檢視合併結果。

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class MergeReport(BaseModel):
    """跨表合併報告"""

    id: str = Field(..., description="報告 ID (UUID)")
    quotation_id: str = Field(..., description="關聯報價單 ID")

    # 來源文件
    quantity_summary_doc_id: Optional[str] = Field(None, description="數量總表文件 ID")
    detail_spec_doc_ids: List[str] = Field(default_factory=list, description="明細規格表文件 ID 列表（按上傳順序）")

    # 合併統計
    total_items: int = Field(0, ge=0, description="合併後總項目數")
    matched_items: int = Field(0, ge=0, description="成功配對項目數")
    unmatched_items: int = Field(0, ge=0, description="未配對項目數（僅在明細表）")
    quantity_only_items: int = Field(0, ge=0, description="僅在數量總表的項目數")

    # 合併詳情
    merge_results: List[MergeResult] = Field(default_factory=list, description="各項目合併結果")

    # 警告訊息
    warnings: List[str] = Field(default_factory=list, description="合併過程警告訊息")

    # 時間戳記
    created_at: datetime = Field(default_factory=datetime.now)
    processing_time_ms: int = Field(0, ge=0, description="處理時間（毫秒）")

    def add_warning(self, message: str):
        """新增警告訊息"""
        self.warnings.append(message)

    def get_match_rate(self) -> float:
        """計算配對率"""
        if self.total_items == 0:
            return 0.0
        return (self.matched_items / self.total_items) * 100
```

---

### 10. SourceDocument 擴充欄位

為現有 SourceDocument 模型新增跨表合併所需欄位：

```python
# 新增至 SourceDocument 模型

class SourceDocument(BaseModel):
    """來源文件資料模型（含跨表合併欄位）"""

    # ... 現有欄位 ...

    # 跨表合併欄位（2025-12-23 新增）
    document_role: DocumentRole = Field(
        DocumentRole.UNKNOWN,
        description="文件角色（數量總表/明細規格表）"
    )
    upload_order: int = Field(
        0,
        ge=0,
        description="上傳順序（用於多明細表合併優先順序）"
    )
    role_detected_by: Literal["filename", "manual", "content"] = Field(
        "filename",
        description="角色偵測方式"
    )
```

---

### 11. BOQItem 擴充欄位

為現有 BOQItem 模型新增跨表合併追蹤欄位：

```python
# 新增至 BOQItem 模型

class BOQItem(BaseModel):
    """BOQ 項目資料模型（含跨表合併欄位）"""

    # ... 現有欄位 ...

    # 跨表合併欄位（2025-12-23 新增）
    item_no_normalized: Optional[str] = Field(
        None,
        description="標準化後的 Item No.（用於跨表配對）"
    )
    source_files: List[str] = Field(
        default_factory=list,
        description="來源文件 ID 列表（多來源時記錄所有來源）"
    )
    merge_status: Optional[MergeStatus] = Field(
        None,
        description="合併狀態"
    )
    qty_from_summary: bool = Field(
        False,
        description="數量是否來自數量總表"
    )
    image_selected_from: Optional[str] = Field(
        None,
        description="圖片選自哪個來源文件 ID"
    )
```

---

### 12. ProcessingTask 擴充

為 ProcessingTask 新增跨表合併任務類型：

```python
# 更新 ProcessingTask.task_type

task_type: Literal[
    "parse_pdf",
    "extract_images",
    "generate_excel",
    "analyze_floor_plan",
    "merge_documents",      # 新增：跨表合併任務
    "parse_quantity_summary" # 新增：解析數量總表
] = Field(..., description="任務類型")
```

---

## 跨表合併驗證規則

### QuantitySummaryItem
| 規則 | 描述 |
|------|------|
| VR-011 | `item_no_raw` 必填，不可為空白 |
| VR-012 | `total_qty` 必須 ≥ 0 |

### MergeResult
| 規則 | 描述 |
|------|------|
| VR-013 | `item_no_normalized` 必填 |
| VR-014 | `status` 必須為有效的 MergeStatus |
| VR-015 | 若 `status` 為 `matched`，`quantity_source` 必填 |

### MergeReport
| 規則 | 描述 |
|------|------|
| VR-016 | `quotation_id` 必須對應有效的 Quotation |
| VR-017 | `matched_items + unmatched_items + quantity_only_items = total_items` |

### SourceDocument (跨表合併)
| 規則 | 描述 |
|------|------|
| VR-018 | 每次上傳最多 1 個 `quantity_summary` 角色文件 |
| VR-019 | 每次上傳最多 10 個 PDF 文件 |
| VR-020 | 所有文件總頁數不超過 200 頁 |

---

## 跨表合併資料流程圖

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           使用者上傳多個 PDF                                   │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐   │
│  │ Bay Tower...Qty.pdf │  │ Casegoods.pdf       │  │ Fabric.pdf          │   │
│  │ (quantity_summary)  │  │ (detail_spec #1)    │  │ (detail_spec #2)    │   │
│  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘   │
└─────────────│─────────────────────────│─────────────────────────│────────────┘
              │                         │                         │
              ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DocumentRoleDetector                                  │
│   根據檔名關鍵字偵測角色 → quantity_summary / detail_spec                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
              ▼                                         ▼
┌─────────────────────────────┐         ┌─────────────────────────────────────┐
│   QuantitySummaryParser     │         │        PDFParserService              │
│   (專用 Gemini Prompt)       │         │   (現有解析流程，產出 BOQItem[])      │
│                             │         │                                      │
│   產出：                     │         │   產出：                             │
│   QuantitySummaryItem[]     │         │   BOQItem[] (detail_spec #1)        │
│   (Item No + Total Qty)     │         │   BOQItem[] (detail_spec #2)        │
└──────────────┬──────────────┘         └──────────────────┬──────────────────┘
               │                                           │
               │                                           │
               └──────────────────┬────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MergeService                                       │
│                                                                              │
│   1. Item No. 標準化 (ItemNormalizer)                                        │
│   2. 建立 quantity_summary 索引 (Item No. → Total Qty)                       │
│   3. 遍歷 detail_spec 項目，依 Item No. 查找數量                              │
│   4. 多明細表欄位合併（upload_order 優先）                                    │
│   5. 圖片選擇（最高解析度）                                                   │
│   6. 產出合併後 BOQItem[] 與 MergeReport                                     │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Quotation                                         │
│   items: BOQItem[] (合併後)                                                  │
│   merge_report_id: str (關聯合併報告)                                         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ExcelGeneratorService                                 │
│   產出惠而蒙格式 15 欄 Excel                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## API Response Models

### 通用回應格式

```python
from pydantic import BaseModel
from typing import Optional, Any, List

class APIResponse(BaseModel):
    """標準 API 回應格式"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None

class PaginatedResponse(BaseModel):
    """分頁回應格式"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
```

### 錯誤回應

```python
class ErrorResponse(BaseModel):
    """錯誤回應格式"""
    error: bool = True
    error_code: str
    message: str  # 繁體中文錯誤訊息
    detail: Optional[str] = None
    timestamp: datetime
```

---

## 記憶體儲存結構

由於系統不使用資料庫，使用記憶體字典儲存：

```python
from typing import Dict
from threading import Lock

class InMemoryStore:
    """記憶體資料儲存"""

    def __init__(self):
        self._documents: Dict[str, SourceDocument] = {}
        self._tasks: Dict[str, ProcessingTask] = {}
        self._quotations: Dict[str, Quotation] = {}
        self._images: Dict[str, ExtractedImage] = {}
        self._lock = Lock()

    def add_document(self, doc: SourceDocument) -> None:
        with self._lock:
            self._documents[doc.id] = doc

    def get_document(self, doc_id: str) -> Optional[SourceDocument]:
        return self._documents.get(doc_id)

    def add_task(self, task: ProcessingTask) -> None:
        with self._lock:
            self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[ProcessingTask]:
        return self._tasks.get(task_id)

    def update_task(self, task_id: str, **updates) -> None:
        with self._lock:
            if task_id in self._tasks:
                for key, value in updates.items():
                    setattr(self._tasks[task_id], key, value)

    # ... 其他 CRUD 方法

# 全域實例
store = InMemoryStore()
```
