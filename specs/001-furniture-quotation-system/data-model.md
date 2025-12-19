# Data Model: 家具報價單系統

**Feature Branch**: `001-furniture-quotation-system`
**Date**: 2025-12-19
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
    """BOQ 項目資料模型"""

    # 主鍵（系統產生）
    id: str = Field(..., description="唯一識別碼 (UUID)")

    # 核心欄位（惠而蒙格式 10 欄，排除價格/金額欄位）
    no: int = Field(..., ge=1, description="序號 (NO.)")
    item_no: str = Field(..., description="項目編號 (Item No.)")
    description: str = Field(..., description="描述 (Description)")
    photo_path: Optional[str] = Field(None, description="圖片檔案路徑 (Photo)")
    dimension: Optional[str] = Field(None, description="尺寸規格 WxDxH mm (Dimension)")
    qty: Optional[float] = Field(None, ge=0, description="數量 (Qty)")
    uom: Optional[str] = Field(None, description="單位 (UOM)，如：ea, m, set")
    note: Optional[str] = Field(None, description="備註 (Note)")
    location: Optional[str] = Field(None, description="位置/區域 (Location)")
    materials_specs: Optional[str] = Field(None, description="材料/規格 (Materials Used / Specs)")

    # 來源追蹤
    source_type: Literal["boq", "floor_plan", "manual"] = Field(
        "boq", description="資料來源類型"
    )
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")
    source_location: Optional[str] = Field(None, description="原始 PDF 中的位置描述")

    # 驗證狀態
    qty_verified: bool = Field(False, description="數量是否已核對")
    qty_source: Optional[Literal["boq", "floor_plan"]] = Field(
        None, description="數量資料來源"
    )

    # 時間戳記
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

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

| 欄位 | 類型 | 必填 | 說明 | 驗證規則 |
|------|------|------|------|----------|
| id | string | ✅ | UUID 格式唯一識別碼 | 系統自動產生 |
| no | int | ✅ | 序號 (NO.) | ≥ 1，系統產生 |
| item_no | string | ✅ | 項目編號 (Item No.) | 不可為空 |
| description | string | ✅ | 描述 (Description) | 不可為空 |
| photo_path | string | ❌ | 圖片檔案路徑 (Photo) | 有效路徑或 null |
| dimension | string | ❌ | 尺寸規格 WxDxH mm (Dimension) | - |
| qty | float | ❌ | 數量 (Qty) | ≥ 0 |
| uom | string | ❌ | 單位 (UOM)，如：ea, m, set | - |
| note | string | ❌ | 備註 (Note) | - |
| location | string | ❌ | 位置/區域 (Location) | - |
| materials_specs | string | ❌ | 材料/規格 (Materials Used / Specs) | - |
| source_type | enum | ✅ | 資料來源：boq/floor_plan/manual | 限定值 |
| source_document_id | string | ✅ | 來源文件 ID | 有效 UUID |
| source_page | int | ❌ | 來源頁碼 | ≥ 1 |

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
        self.items_with_photo = sum(1 for item in self.items if item.photo_path)
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
│  │  photo_path ────────────────────────────────────┐               │    │
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
> 注意：排除價格/金額欄位（Unit Rate, Amount, Unit CBM, Total CBM），這些由用戶手動填寫

| Excel 欄位 | 資料模型欄位 | 說明 |
|------------|--------------|------|
| A: NO. | `BOQItem.no` | 序號（系統產生） |
| B: Item No. | `BOQItem.item_no` | 項目編號 |
| C: Description | `BOQItem.description` | 描述 |
| D: Photo | `BOQItem.photo_path` → 嵌入圖片 | 圖片儲存格 |
| E: Dimension | `BOQItem.dimension` | 尺寸規格 WxDxH (mm) |
| F: Qty | `BOQItem.qty` | 數量 |
| G: UOM | `BOQItem.uom` | 單位 |
| H: Note | `BOQItem.note` | 備註 |
| I: Location | `BOQItem.location` | 位置 |
| J: Materials Used/Specs | `BOQItem.materials_specs` | 材料/規格 |

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
