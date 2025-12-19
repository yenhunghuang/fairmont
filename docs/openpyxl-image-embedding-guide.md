# Python openpyxl 嵌入圖片到 Excel 最佳實踐指南

**建立日期**: 2025-12-19
**適用專案**: 家具報價單系統 (Furniture Quotation System)
**目標格式**: 惠而蒙格式 Excel 報價單

---

## 目錄

1. [圖片嵌入基礎](#1-圖片嵌入基礎)
2. [圖片大小調整與儲存格對齊](#2-圖片大小調整與儲存格對齊)
3. [支援的圖片格式](#3-支援的圖片格式)
4. [大量圖片嵌入的效能考量](#4-大量圖片嵌入的效能考量)
5. [產出 xlsx 檔案的最佳實踐](#5-產出-xlsx-檔案的最佳實踐)
6. [惠而蒙格式報價單實作](#6-惠而蒙格式報價單實作)

---

## 1. 圖片嵌入基礎

### 1.1 基本圖片嵌入方法

openpyxl 提供 `Image` 類別用於在 Excel 中嵌入圖片。

```python
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter

# 建立工作簿
wb = Workbook()
ws = wb.active

# 方法 1: 從檔案路徑嵌入圖片
img = Image('path/to/image.jpg')
ws.add_image(img, 'C2')  # 嵌入到 C2 儲存格

# 方法 2: 從記憶體 (BytesIO) 嵌入圖片
from io import BytesIO
from PIL import Image as PILImage

# 從 PDF 提取或處理後的圖片
pil_img = PILImage.open('image.jpg')
img_byte_arr = BytesIO()
pil_img.save(img_byte_arr, format='PNG')
img_byte_arr.seek(0)

img = Image(img_byte_arr)
ws.add_image(img, 'C2')

wb.save('output.xlsx')
```

### 1.2 座標系統說明

openpyxl 使用兩種座標系統：

```python
# 方式 1: 儲存格名稱 (推薦用於固定位置)
ws.add_image(img, 'C2')  # C 欄第 2 列

# 方式 2: 數字座標 (推薦用於動態生成)
from openpyxl.utils import get_column_letter

row = 2
col = 3  # C 欄
cell_address = f'{get_column_letter(col)}{row}'
ws.add_image(img, cell_address)
```

---

## 2. 圖片大小調整與儲存格對齊

### 2.1 圖片尺寸調整策略

```python
from openpyxl.drawing.image import Image
from PIL import Image as PILImage
from io import BytesIO

def resize_image_to_fit_cell(
    pil_image: PILImage.Image,
    max_width_px: int = 150,
    max_height_px: int = 150,
    maintain_aspect_ratio: bool = True
) -> Image:
    """
    調整圖片大小以適應儲存格

    Args:
        pil_image: PIL Image 物件
        max_width_px: 最大寬度（像素）
        max_height_px: 最大高度（像素）
        maintain_aspect_ratio: 是否維持長寬比

    Returns:
        openpyxl.drawing.image.Image 物件
    """
    original_width, original_height = pil_image.size

    if maintain_aspect_ratio:
        # 計算縮放比例（保持長寬比）
        width_ratio = max_width_px / original_width
        height_ratio = max_height_px / original_height
        scale_ratio = min(width_ratio, height_ratio)

        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)
    else:
        # 強制縮放到指定大小
        new_width = max_width_px
        new_height = max_height_px

    # 調整圖片大小（使用高品質重採樣）
    resized_image = pil_image.resize(
        (new_width, new_height),
        PILImage.Resampling.LANCZOS  # 高品質縮放演算法
    )

    # 轉換為 BytesIO 供 openpyxl 使用
    img_byte_arr = BytesIO()
    resized_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return Image(img_byte_arr)


# 使用範例
pil_img = PILImage.open('large_image.jpg')
img = resize_image_to_fit_cell(pil_img, max_width_px=120, max_height_px=120)
ws.add_image(img, 'C2')
```

### 2.2 圖片與儲存格對齊

#### 選項 1: 調整圖片大小配合固定儲存格

```python
from openpyxl.utils.units import pixels_to_EMU

# 設定儲存格尺寸（以點為單位，1點 = 1/72 英吋）
ws.column_dimensions['C'].width = 20  # 約 150 像素
ws.row_dimensions[2].height = 100  # 約 133 像素

# 嵌入已調整大小的圖片
img = resize_image_to_fit_cell(pil_img, max_width_px=150, max_height_px=133)
ws.add_image(img, 'C2')
```

#### 選項 2: 動態調整儲存格尺寸配合圖片

```python
def adjust_cell_for_image(
    ws,
    row: int,
    col: int,
    image_width_px: int,
    image_height_px: int,
    padding_px: int = 5
):
    """
    調整儲存格尺寸以容納圖片

    Excel 單位轉換：
    - 欄寬單位: 字元寬度 (1 單位 ≈ 7.5 像素，字型 11pt Calibri)
    - 列高單位: 點 (1 點 = 1.33 像素)
    """
    from openpyxl.utils import get_column_letter

    col_letter = get_column_letter(col)

    # 計算所需欄寬（加上內距）
    required_width_chars = (image_width_px + 2 * padding_px) / 7.5
    ws.column_dimensions[col_letter].width = required_width_chars

    # 計算所需列高（加上內距）
    required_height_points = (image_height_px + 2 * padding_px) / 1.33
    ws.row_dimensions[row].height = required_height_points


# 使用範例
img_width, img_height = 120, 120
adjust_cell_for_image(ws, row=2, col=3, image_width_px=img_width, image_height_px=img_height)

img = resize_image_to_fit_cell(pil_img, max_width_px=img_width, max_height_px=img_height)
ws.add_image(img, 'C2')
```

### 2.3 圖片錨點定位（進階）

openpyxl 使用錨點系統來精確定位圖片。

```python
from openpyxl.drawing.spreadsheet_drawing import TwoCellAnchor, OneCellAnchor
from openpyxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU

# 方法 1: 雙儲存格錨點（圖片會隨儲存格縮放）
# 這是預設行為，add_image() 自動處理

# 方法 2: 單儲存格錨點（圖片大小固定，不隨儲存格縮放）
img = Image('image.jpg')
img.anchor = 'C2'  # 起始儲存格

# 手動設定圖片偏移（從儲存格左上角）
# 單位為 EMU (English Metric Units, 1 英吋 = 914400 EMU)
offset_x_px = 5  # 向右偏移 5 像素
offset_y_px = 5  # 向下偏移 5 像素

# 注意：openpyxl 預設不直接支援像素偏移，需使用 img.width/height 屬性
# 或直接操作底層 XML（進階用法，不推薦）

ws.add_image(img, 'C2')
```

---

## 3. 支援的圖片格式

### 3.1 openpyxl 原生支援格式

openpyxl 支援以下圖片格式：

| 格式 | 副檔名 | 推薦用於 | 備註 |
|------|--------|---------|------|
| PNG | `.png` | 透明背景、品質要求高 | **推薦**：無損壓縮，支援透明度 |
| JPEG | `.jpg`, `.jpeg` | 照片、檔案大小敏感 | 有損壓縮，不支援透明度 |
| GIF | `.gif` | 簡單圖形、動畫 | 256 色限制，少用於報價單 |
| BMP | `.bmp` | 原始圖片 | 檔案過大，不推薦 |

### 3.2 格式轉換最佳實踐

```python
from PIL import Image as PILImage
from io import BytesIO
from openpyxl.drawing.image import Image

def convert_image_to_png(image_source) -> Image:
    """
    將任意格式圖片轉換為 PNG 格式

    Args:
        image_source: 可以是檔案路徑、BytesIO、或 PIL Image 物件

    Returns:
        openpyxl Image 物件（PNG 格式）
    """
    # 載入圖片
    if isinstance(image_source, PILImage.Image):
        pil_img = image_source
    elif isinstance(image_source, (str, BytesIO)):
        pil_img = PILImage.open(image_source)
    else:
        raise TypeError(f"不支援的圖片來源類型: {type(image_source)}")

    # 處理 RGBA 模式（PNG 透明度）
    if pil_img.mode in ('RGBA', 'LA', 'P'):
        # 建立白色背景
        background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
        if pil_img.mode == 'P':
            pil_img = pil_img.convert('RGBA')
        background.paste(pil_img, mask=pil_img.split()[-1])  # 使用 alpha 通道作為遮罩
        pil_img = background
    elif pil_img.mode != 'RGB':
        pil_img = pil_img.convert('RGB')

    # 轉換為 PNG BytesIO
    img_byte_arr = BytesIO()
    pil_img.save(img_byte_arr, format='PNG', optimize=True)
    img_byte_arr.seek(0)

    return Image(img_byte_arr)


# 使用範例
# 從 PDF 提取的圖片可能是各種格式
img = convert_image_to_png('extracted_from_pdf.webp')
ws.add_image(img, 'C2')
```

### 3.3 從 PDF 提取圖片（PyMuPDF/fitz）

```python
import fitz  # PyMuPDF
from PIL import Image as PILImage
from io import BytesIO

def extract_images_from_pdf(pdf_path: str) -> list[PILImage.Image]:
    """
    從 PDF 提取所有圖片

    Returns:
        PIL Image 物件列表
    """
    images = []
    pdf_document = fitz.open(pdf_path)

    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]  # 圖片的 xref 編號
            base_image = pdf_document.extract_image(xref)

            image_bytes = base_image["image"]
            image_ext = base_image["ext"]  # 格式：png, jpg, etc.

            # 轉換為 PIL Image
            pil_img = PILImage.open(BytesIO(image_bytes))
            images.append(pil_img)

    pdf_document.close()
    return images


# 使用範例
extracted_images = extract_images_from_pdf('boq_document.pdf')
for idx, pil_img in enumerate(extracted_images):
    img = resize_image_to_fit_cell(pil_img, max_width_px=120, max_height_px=120)
    ws.add_image(img, f'C{idx + 2}')
```

---

## 4. 大量圖片嵌入的效能考量

### 4.1 效能瓶頸分析

嵌入大量圖片時，主要效能瓶頸：

1. **圖片讀取與解碼** (30-40% 時間)
2. **圖片縮放處理** (20-30% 時間)
3. **Excel 寫入與序列化** (30-40% 時間)
4. **記憶體消耗** (主要風險)

### 4.2 最佳化策略

#### 策略 1: 批次處理與記憶體管理

```python
from typing import Iterator
import gc

def process_images_in_batches(
    image_sources: list,
    batch_size: int = 50
) -> Iterator[list]:
    """
    批次處理圖片以避免記憶體溢出

    Args:
        image_sources: 圖片來源列表（路徑或 BytesIO）
        batch_size: 每批處理數量

    Yields:
        處理後的圖片批次
    """
    for i in range(0, len(image_sources), batch_size):
        batch = image_sources[i:i + batch_size]
        processed_batch = []

        for img_source in batch:
            pil_img = PILImage.open(img_source)
            processed_img = resize_image_to_fit_cell(pil_img)
            processed_batch.append(processed_img)

            # 關閉 PIL 圖片釋放記憶體
            pil_img.close()

        yield processed_batch

        # 強制垃圾回收
        gc.collect()


# 使用範例
image_paths = [f'image_{i}.jpg' for i in range(200)]  # 200 張圖片

row = 2
for batch in process_images_in_batches(image_paths, batch_size=50):
    for img in batch:
        ws.add_image(img, f'C{row}')
        row += 1
```

#### 策略 2: 圖片預處理與快取

```python
import hashlib
from pathlib import Path
from functools import lru_cache

class ImageCache:
    """圖片快取管理器"""

    def __init__(self, cache_dir: str = '.image_cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_path(self, image_bytes: bytes) -> Path:
        """根據圖片內容生成快取路徑"""
        img_hash = hashlib.md5(image_bytes).hexdigest()
        return self.cache_dir / f'{img_hash}.png'

    def get_or_process(
        self,
        image_bytes: bytes,
        max_width: int = 120,
        max_height: int = 120
    ) -> bytes:
        """獲取快取或處理新圖片"""
        cache_path = self.get_cache_path(image_bytes)

        if cache_path.exists():
            # 從快取讀取
            return cache_path.read_bytes()

        # 處理新圖片
        pil_img = PILImage.open(BytesIO(image_bytes))
        processed_img = resize_image_to_fit_cell(pil_img, max_width, max_height)

        # 儲存到快取
        processed_img_bytes = BytesIO()
        PILImage.open(BytesIO(image_bytes)).save(processed_img_bytes, format='PNG')
        cache_path.write_bytes(processed_img_bytes.getvalue())

        return processed_img_bytes.getvalue()


# 使用範例
cache = ImageCache()

for img_path in image_paths:
    img_bytes = Path(img_path).read_bytes()
    cached_img_bytes = cache.get_or_process(img_bytes)

    img = Image(BytesIO(cached_img_bytes))
    ws.add_image(img, f'C{row}')
    row += 1
```

#### 策略 3: 並行處理（謹慎使用）

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

def process_single_image(
    img_path: str,
    max_width: int = 120,
    max_height: int = 120
) -> Tuple[str, bytes]:
    """處理單一圖片（執行緒安全）"""
    pil_img = PILImage.open(img_path)

    # 調整大小
    resized = resize_image_to_fit_cell(pil_img, max_width, max_height)

    # 轉換為 bytes
    img_bytes = BytesIO()
    PILImage.open(img_path).save(img_bytes, format='PNG')

    pil_img.close()
    return img_path, img_bytes.getvalue()


def process_images_parallel(
    image_paths: list[str],
    max_workers: int = 4
) -> dict[str, bytes]:
    """並行處理圖片"""
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_image, path): path
            for path in image_paths
        }

        for future in as_completed(futures):
            img_path, img_bytes = future.result()
            results[img_path] = img_bytes

    return results


# 使用範例（注意：openpyxl 本身不是執行緒安全的，僅處理圖片可並行）
processed_images = process_images_parallel(image_paths, max_workers=4)

row = 2
for img_path in image_paths:
    img = Image(BytesIO(processed_images[img_path]))
    ws.add_image(img, f'C{row}')
    row += 1
```

### 4.3 效能基準測試

```python
import time
from typing import Callable

def benchmark_image_insertion(
    func: Callable,
    num_images: int = 100,
    **kwargs
) -> dict:
    """
    效能基準測試

    Returns:
        包含執行時間、記憶體使用等指標的字典
    """
    import tracemalloc

    tracemalloc.start()
    start_time = time.time()

    # 執行函數
    result = func(num_images=num_images, **kwargs)

    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        'execution_time_seconds': end_time - start_time,
        'memory_current_mb': current / 1024 / 1024,
        'memory_peak_mb': peak / 1024 / 1024,
        'images_per_second': num_images / (end_time - start_time),
        'result': result
    }


# 使用範例
metrics = benchmark_image_insertion(
    func=lambda num_images: [
        ws.add_image(
            resize_image_to_fit_cell(PILImage.open(f'image_{i}.jpg')),
            f'C{i+2}'
        )
        for i in range(num_images)
    ],
    num_images=100
)

print(f"處理 100 張圖片：")
print(f"  執行時間: {metrics['execution_time_seconds']:.2f} 秒")
print(f"  峰值記憶體: {metrics['memory_peak_mb']:.2f} MB")
print(f"  處理速度: {metrics['images_per_second']:.2f} 張/秒")
```

**效能建議**：

- **50 張圖片以下**：直接處理，無需特殊優化
- **50-200 張圖片**：使用批次處理 + 記憶體管理
- **200 張圖片以上**：批次處理 + 快取 + 考慮分割為多個工作表

---

## 5. 產出 xlsx 檔案的最佳實踐

### 5.1 工作簿設定

```python
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from datetime import datetime

def create_optimized_workbook() -> Workbook:
    """建立最佳化的工作簿"""
    wb = Workbook()
    ws = wb.active

    # 設定工作表名稱
    ws.title = "報價單"

    # 設定預設字型（全域）
    default_font = Font(name='Calibri', size=11)

    # 設定預設對齊方式
    default_alignment = Alignment(
        horizontal='center',
        vertical='center',
        wrap_text=True  # 自動換行
    )

    # 凍結首列（標題列）
    ws.freeze_panes = 'A2'

    return wb


# 使用範例
wb = create_optimized_workbook()
ws = wb.active
```

### 5.2 樣式最佳化

```python
from openpyxl.styles import NamedStyle

def create_reusable_styles(wb: Workbook):
    """建立可重複使用的樣式（效能優化）"""

    # 標題列樣式
    header_style = NamedStyle(name="header")
    header_style.font = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
    header_style.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    header_style.alignment = Alignment(horizontal='center', vertical='center')
    header_style.border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # 資料列樣式
    data_style = NamedStyle(name="data")
    data_style.font = Font(name='Calibri', size=11)
    data_style.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    data_style.border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # 註冊樣式到工作簿
    wb.add_named_style(header_style)
    wb.add_named_style(data_style)


def apply_styles_efficiently(ws, start_row: int, end_row: int):
    """高效應用樣式（避免逐儲存格設定）"""
    for row in ws.iter_rows(min_row=start_row, max_row=end_row):
        for cell in row:
            cell.style = 'data'  # 使用命名樣式


# 使用範例
create_reusable_styles(wb)
apply_styles_efficiently(ws, start_row=2, end_row=100)
```

### 5.3 檔案儲存最佳化

```python
from openpyxl.writer.excel import save_workbook
from pathlib import Path

def save_excel_optimized(
    wb: Workbook,
    output_path: str,
    compress: bool = True
) -> Path:
    """
    最佳化儲存 Excel 檔案

    Args:
        wb: 工作簿物件
        output_path: 輸出路徑
        compress: 是否壓縮（減少檔案大小）

    Returns:
        儲存的檔案路徑
    """
    output_path = Path(output_path)

    # 確保目錄存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 儲存前優化
    # 1. 移除未使用的樣式
    # 2. 計算公式（如有）

    # 儲存工作簿
    if compress:
        # openpyxl 預設使用 ZIP 壓縮，無需額外設定
        wb.save(output_path)
    else:
        wb.save(output_path)

    # 驗證檔案
    if not output_path.exists():
        raise IOError(f"檔案儲存失敗: {output_path}")

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Excel 檔案已儲存: {output_path} ({file_size_mb:.2f} MB)")

    return output_path


# 使用範例
output_file = save_excel_optimized(
    wb,
    output_path='output/quotation_20251219.xlsx',
    compress=True
)
```

### 5.4 檔案大小優化技巧

```python
def optimize_workbook_size(wb: Workbook) -> Workbook:
    """
    優化工作簿檔案大小

    技巧：
    1. 壓縮圖片（已在上傳時處理）
    2. 移除空白工作表
    3. 清除未使用的樣式
    4. 避免過度格式化
    """
    # 移除空白工作表（保留至少一個）
    sheets_to_remove = []
    for sheet in wb.worksheets:
        if sheet.max_row == 1 and sheet.max_column == 1:
            if len(wb.worksheets) > 1:
                sheets_to_remove.append(sheet.title)

    for sheet_name in sheets_to_remove:
        wb.remove(wb[sheet_name])

    # 清除未使用的行列（openpyxl 自動處理）

    return wb


# 使用範例
wb = optimize_workbook_size(wb)
wb.save('optimized_quotation.xlsx')
```

---

## 6. 惠而蒙格式報價單實作

### 6.1 完整實作範例

```python
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side, NamedStyle
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
from io import BytesIO
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BOQItem:
    """BOQ 項目資料模型"""
    item_no: str  # Item No.
    description: str  # Description
    photo: Optional[PILImage.Image]  # Photo (PIL Image)
    dimension: str  # Dimension
    qty: int  # Quantity
    uom: str  # Unit of Measurement
    location: str  # Location
    materials_specs: str  # Materials Used/Specs


class FairmontQuotationGenerator:
    """惠而蒙格式報價單生成器"""

    # 欄位定義（按順序）
    COLUMNS = [
        'Item No.',
        'Description',
        'Photo',
        'Dimension',
        'Qty',
        'UOM',
        'Location',
        'Materials Used/Specs'
    ]

    # 欄位對應索引（1-based）
    COL_ITEM_NO = 1  # A
    COL_DESCRIPTION = 2  # B
    COL_PHOTO = 3  # C
    COL_DIMENSION = 4  # D
    COL_QTY = 5  # E
    COL_UOM = 6  # F
    COL_LOCATION = 7  # G
    COL_MATERIALS_SPECS = 8  # H

    # 欄位寬度設定（字元單位）
    COLUMN_WIDTHS = {
        1: 10,   # Item No.
        2: 30,   # Description
        3: 20,   # Photo
        4: 15,   # Dimension
        5: 8,    # Qty
        6: 10,   # UOM
        7: 20,   # Location
        8: 35    # Materials Used/Specs
    }

    # 圖片設定
    IMAGE_MAX_WIDTH = 120  # 像素
    IMAGE_MAX_HEIGHT = 120  # 像素
    ROW_HEIGHT_WITH_IMAGE = 90  # 點（約 120 像素）

    def __init__(self):
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "報價單"
        self._setup_styles()
        self._setup_columns()

    def _setup_styles(self):
        """設定樣式"""
        # 標題列樣式
        header_style = NamedStyle(name="header")
        header_style.font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
        header_style.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_style.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        header_style.border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )

        # 資料列樣式
        data_style = NamedStyle(name="data")
        data_style.font = Font(name='Arial', size=11)
        data_style.alignment = Alignment(
            horizontal='center',
            vertical='center',
            wrap_text=True
        )
        data_style.border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC')
        )

        # 文字列樣式（Description, Materials/Specs 靠左對齊）
        text_style = NamedStyle(name="text")
        text_style.font = Font(name='Arial', size=11)
        text_style.alignment = Alignment(
            horizontal='left',
            vertical='center',
            wrap_text=True
        )
        text_style.border = data_style.border

        self.wb.add_named_style(header_style)
        self.wb.add_named_style(data_style)
        self.wb.add_named_style(text_style)

    def _setup_columns(self):
        """設定欄位寬度與標題"""
        # 設定欄寬
        for col_idx, width in self.COLUMN_WIDTHS.items():
            col_letter = get_column_letter(col_idx)
            self.ws.column_dimensions[col_letter].width = width

        # 寫入標題列
        for col_idx, col_name in enumerate(self.COLUMNS, start=1):
            cell = self.ws.cell(row=1, column=col_idx, value=col_name)
            cell.style = 'header'

        # 凍結標題列
        self.ws.freeze_panes = 'A2'

        # 設定標題列高度
        self.ws.row_dimensions[1].height = 25

    def _resize_image_for_cell(self, pil_image: PILImage.Image) -> Image:
        """調整圖片大小以適應儲存格"""
        original_width, original_height = pil_image.size

        # 計算縮放比例（保持長寬比）
        width_ratio = self.IMAGE_MAX_WIDTH / original_width
        height_ratio = self.IMAGE_MAX_HEIGHT / original_height
        scale_ratio = min(width_ratio, height_ratio)

        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)

        # 調整大小
        resized_image = pil_image.resize(
            (new_width, new_height),
            PILImage.Resampling.LANCZOS
        )

        # 轉換為 PNG BytesIO
        img_byte_arr = BytesIO()
        resized_image.save(img_byte_arr, format='PNG', optimize=True)
        img_byte_arr.seek(0)

        return Image(img_byte_arr)

    def add_item(self, item: BOQItem, row: int):
        """
        新增 BOQ 項目到報價單

        Args:
            item: BOQ 項目資料
            row: 列號（從 2 開始，1 為標題列）
        """
        # 寫入文字資料
        self.ws.cell(row=row, column=self.COL_ITEM_NO, value=item.item_no).style = 'data'
        self.ws.cell(row=row, column=self.COL_DESCRIPTION, value=item.description).style = 'text'
        self.ws.cell(row=row, column=self.COL_DIMENSION, value=item.dimension).style = 'data'
        self.ws.cell(row=row, column=self.COL_QTY, value=item.qty).style = 'data'
        self.ws.cell(row=row, column=self.COL_UOM, value=item.uom).style = 'data'
        self.ws.cell(row=row, column=self.COL_LOCATION, value=item.location).style = 'data'
        self.ws.cell(row=row, column=self.COL_MATERIALS_SPECS, value=item.materials_specs).style = 'text'

        # 設定列高（為圖片預留空間）
        self.ws.row_dimensions[row].height = self.ROW_HEIGHT_WITH_IMAGE

        # 嵌入圖片
        if item.photo:
            try:
                img = self._resize_image_for_cell(item.photo)
                cell_address = f'{get_column_letter(self.COL_PHOTO)}{row}'
                self.ws.add_image(img, cell_address)
            except Exception as e:
                print(f"警告：第 {row} 列圖片嵌入失敗 - {e}")
                self.ws.cell(row=row, column=self.COL_PHOTO, value="[圖片載入失敗]").style = 'data'
        else:
            # 無圖片時顯示佔位符
            self.ws.cell(row=row, column=self.COL_PHOTO, value="[無圖片]").style = 'data'

    def add_items_batch(self, items: List[BOQItem], start_row: int = 2):
        """
        批次新增 BOQ 項目

        Args:
            items: BOQ 項目列表
            start_row: 起始列號（預設從第 2 列開始）
        """
        for idx, item in enumerate(items):
            row = start_row + idx
            self.add_item(item, row)

            # 每 50 筆進行一次垃圾回收
            if (idx + 1) % 50 == 0:
                import gc
                gc.collect()
                print(f"已處理 {idx + 1}/{len(items)} 筆項目...")

    def save(self, output_path: str) -> str:
        """
        儲存報價單

        Returns:
            儲存的檔案路徑
        """
        from pathlib import Path

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.wb.save(output_path)

        file_size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"報價單已儲存: {output_path} ({file_size_mb:.2f} MB)")

        return str(output_path)

    def add_metadata(self, project_name: str = "", created_by: str = ""):
        """新增元資料（頁首說明）"""
        # 在標題列上方插入元資料列
        self.ws.insert_rows(1, amount=3)

        # 調整標題列位置（現在在第 4 列）
        self.ws.freeze_panes = 'A5'

        # 寫入元資料
        self.ws.cell(row=1, column=1, value=f"專案名稱: {project_name}")
        self.ws.cell(row=2, column=1, value=f"產生日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.ws.cell(row=3, column=1, value=f"產生者: {created_by or '惠而蒙報價單系統'}")

        # 合併儲存格（美觀）
        self.ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(self.COLUMNS))
        self.ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(self.COLUMNS))
        self.ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(self.COLUMNS))

        # 樣式
        for row in [1, 2, 3]:
            cell = self.ws.cell(row=row, column=1)
            cell.font = Font(name='Arial', size=10, italic=True)
            cell.alignment = Alignment(horizontal='left', vertical='center')


# ==================== 使用範例 ====================

def example_usage():
    """完整使用範例"""

    # 1. 準備測試資料
    sample_items = [
        BOQItem(
            item_no="A-001",
            description="辦公桌",
            photo=PILImage.open('desk.jpg') if Path('desk.jpg').exists() else None,
            dimension="1800W x 800D x 750H mm",
            qty=5,
            uom="張",
            location="1F 辦公室",
            materials_specs="桌面: E1 防火板 25mm\n桌腳: 鋼製烤漆腳架"
        ),
        BOQItem(
            item_no="A-002",
            description="辦公椅",
            photo=PILImage.open('chair.jpg') if Path('chair.jpg').exists() else None,
            dimension="680W x 680D x 1100H mm",
            qty=5,
            uom="張",
            location="1F 辦公室",
            materials_specs="椅面: 網布透氣椅背\n底座: 鋁合金五爪腳\n扶手: PP 塑膠扶手"
        ),
        BOQItem(
            item_no="B-001",
            description="會議桌",
            photo=None,  # 無圖片
            dimension="3600W x 1200D x 750H mm",
            qty=1,
            uom="張",
            location="2F 會議室",
            materials_specs="桌面: 美耐板 40mm\n桌腳: 不鏽鋼桌腳"
        )
    ]

    # 2. 建立報價單生成器
    generator = FairmontQuotationGenerator()

    # 3. 新增元資料（選用）
    generator.add_metadata(
        project_name="惠而蒙大樓裝修案",
        created_by="專案管理部"
    )

    # 4. 批次新增項目
    # 注意：如果使用了 add_metadata，需要從第 5 列開始（1-3 元資料，4 標題）
    start_row = 5 if generator.ws.max_row > 1 else 2
    generator.add_items_batch(sample_items, start_row=start_row)

    # 5. 儲存檔案
    output_file = generator.save('output/fairmont_quotation_20251219.xlsx')

    print(f"\n報價單生成完成！")
    print(f"檔案位置: {output_file}")
    print(f"總計項目: {len(sample_items)} 筆")


if __name__ == '__main__':
    example_usage()
```

### 6.2 與 PDF 解析整合

```python
from typing import List, Dict, Any
import fitz  # PyMuPDF

class PDFToBOQConverter:
    """PDF 轉 BOQ 項目轉換器（與 Gemini API 整合）"""

    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        # 初始化 Gemini API
        # (實際實作見 backend/app/services/pdf_parser.py)

    def extract_boq_from_pdf(self, pdf_path: str) -> List[BOQItem]:
        """
        從 PDF 提取 BOQ 項目

        流程：
        1. 使用 PyMuPDF 提取圖片
        2. 使用 Gemini API 解析 BOQ 表格資料
        3. 將圖片與資料配對
        4. 轉換為 BOQItem 物件
        """
        # 步驟 1: 提取圖片
        images = self._extract_images_from_pdf(pdf_path)

        # 步驟 2: 呼叫 Gemini API 解析 BOQ 資料
        boq_data = self._parse_boq_with_gemini(pdf_path)

        # 步驟 3: 配對圖片與資料
        items = self._match_images_to_items(boq_data, images)

        return items

    def _extract_images_from_pdf(self, pdf_path: str) -> Dict[int, PILImage.Image]:
        """提取 PDF 中的所有圖片"""
        images = {}
        pdf_document = fitz.open(pdf_path)

        image_counter = 0
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            image_list = page.get_images(full=True)

            for img_info in image_list:
                xref = img_info[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]

                pil_img = PILImage.open(BytesIO(image_bytes))
                images[image_counter] = pil_img
                image_counter += 1

        pdf_document.close()
        return images

    def _parse_boq_with_gemini(self, pdf_path: str) -> List[Dict[str, Any]]:
        """使用 Gemini API 解析 BOQ 資料（佔位符）"""
        # 實際實作見 backend/app/services/pdf_parser.py
        # 這裡返回模擬資料
        return [
            {
                'item_no': 'A-001',
                'description': '辦公桌',
                'dimension': '1800W x 800D x 750H mm',
                'qty': 5,
                'uom': '張',
                'location': '1F 辦公室',
                'materials_specs': '桌面: E1 防火板',
                'image_index': 0  # 對應 images 字典的 key
            }
        ]

    def _match_images_to_items(
        self,
        boq_data: List[Dict[str, Any]],
        images: Dict[int, PILImage.Image]
    ) -> List[BOQItem]:
        """配對圖片與 BOQ 資料"""
        items = []

        for data in boq_data:
            image_index = data.get('image_index')
            photo = images.get(image_index) if image_index is not None else None

            item = BOQItem(
                item_no=data['item_no'],
                description=data['description'],
                photo=photo,
                dimension=data['dimension'],
                qty=data['qty'],
                uom=data['uom'],
                location=data['location'],
                materials_specs=data['materials_specs']
            )
            items.append(item)

        return items


# 完整工作流程範例
def full_workflow_example():
    """完整工作流程：PDF -> BOQ 項目 -> Excel 報價單"""

    # 1. 從 PDF 提取 BOQ 項目
    converter = PDFToBOQConverter(gemini_api_key="YOUR_API_KEY")
    boq_items = converter.extract_boq_from_pdf('input/boq_document.pdf')

    # 2. 生成 Excel 報價單
    generator = FairmontQuotationGenerator()
    generator.add_metadata(project_name="惠而蒙專案")
    generator.add_items_batch(boq_items, start_row=5)

    # 3. 儲存
    output_file = generator.save('output/quotation.xlsx')

    print(f"工作流程完成！產出檔案: {output_file}")
```

### 6.3 錯誤處理與驗證

```python
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuotationValidator:
    """報價單資料驗證器"""

    @staticmethod
    def validate_boq_item(item: BOQItem) -> tuple[bool, Optional[str]]:
        """
        驗證 BOQ 項目資料完整性

        Returns:
            (是否有效, 錯誤訊息)
        """
        # 必填欄位檢查
        if not item.item_no or not item.item_no.strip():
            return False, "Item No. 不可為空"

        if not item.description or not item.description.strip():
            return False, "Description 不可為空"

        if item.qty is None or item.qty < 0:
            return False, "Qty 必須為非負數"

        if not item.uom or not item.uom.strip():
            return False, "UOM 不可為空"

        # 選用欄位警告
        if not item.dimension:
            logger.warning(f"Item {item.item_no}: Dimension 為空")

        if not item.location:
            logger.warning(f"Item {item.item_no}: Location 為空")

        if not item.photo:
            logger.warning(f"Item {item.item_no}: Photo 為空")

        return True, None

    @staticmethod
    def validate_items_batch(items: List[BOQItem]) -> tuple[List[BOQItem], List[str]]:
        """
        批次驗證 BOQ 項目

        Returns:
            (有效項目列表, 錯誤訊息列表)
        """
        valid_items = []
        errors = []

        for idx, item in enumerate(items):
            is_valid, error_msg = QuotationValidator.validate_boq_item(item)

            if is_valid:
                valid_items.append(item)
            else:
                errors.append(f"第 {idx + 1} 筆項目錯誤: {error_msg}")
                logger.error(f"驗證失敗 - Item {idx + 1}: {error_msg}")

        return valid_items, errors


# 使用範例（加入驗證）
def example_with_validation():
    """包含驗證的完整範例"""

    # 準備資料（包含無效項目）
    sample_items = [
        BOQItem(
            item_no="A-001",
            description="辦公桌",
            photo=None,
            dimension="1800W x 800D x 750H mm",
            qty=5,
            uom="張",
            location="1F 辦公室",
            materials_specs="E1 防火板"
        ),
        BOQItem(
            item_no="",  # 無效：Item No. 為空
            description="辦公椅",
            photo=None,
            dimension="680W x 680D x 1100H mm",
            qty=3,
            uom="張",
            location="1F 辦公室",
            materials_specs="網布椅背"
        ),
        BOQItem(
            item_no="B-001",
            description="會議桌",
            photo=None,
            dimension="3600W x 1200D x 750H mm",
            qty=-1,  # 無效：數量為負數
            uom="張",
            location="2F 會議室",
            materials_specs="美耐板"
        )
    ]

    # 驗證
    valid_items, errors = QuotationValidator.validate_items_batch(sample_items)

    if errors:
        print("資料驗證發現錯誤：")
        for error in errors:
            print(f"  - {error}")
        print(f"\n有效項目數: {len(valid_items)}/{len(sample_items)}")

    # 僅處理有效項目
    if valid_items:
        generator = FairmontQuotationGenerator()
        generator.add_items_batch(valid_items)
        generator.save('output/validated_quotation.xlsx')
        print(f"\n報價單已生成（僅包含 {len(valid_items)} 筆有效項目）")
    else:
        print("\n錯誤：無有效項目可生成報價單")
```

---

## 總結與建議

### 關鍵要點

1. **圖片嵌入**
   - 使用 `openpyxl.drawing.image.Image` 類別
   - 從記憶體 (BytesIO) 嵌入圖片效能最佳
   - 座標使用儲存格名稱（如 'C2'）最直觀

2. **圖片調整**
   - 使用 PIL/Pillow 預處理圖片
   - 建議統一調整為 120x120 像素
   - 使用 `LANCZOS` 重採樣演算法保持品質

3. **支援格式**
   - 推薦使用 PNG（無損、透明支援）
   - JPEG 適合照片（檔案較小）
   - 統一轉換為 PNG 可避免相容性問題

4. **效能優化**
   - 50 張圖片以下：直接處理
   - 50-200 張：批次處理 + 記憶體管理
   - 200 張以上：快取 + 分批儲存

5. **檔案產出**
   - 使用命名樣式（NamedStyle）提升效能
   - 壓縮預設啟用（ZIP 壓縮）
   - 檔案大小主要受圖片影響

6. **惠而蒙格式**
   - 8 個標準欄位必須完整
   - Photo 欄位寬度建議 20 字元（約 150 像素）
   - 列高設定 90 點（約 120 像素）以容納圖片

### 專案整合建議

對於家具報價單系統，建議採用以下架構：

```
backend/app/services/excel_generator.py
├── FairmontQuotationGenerator  # 主要生成器類別
├── QuotationValidator  # 資料驗證
└── ImageProcessor  # 圖片處理工具

backend/app/models/boq_item.py
└── BOQItem  # 資料模型（與本指南一致）
```

**參考實作**：本指南中的 `FairmontQuotationGenerator` 類別可直接作為 `backend/app/services/excel_generator.py` 的基礎實作。

---

**版本資訊**

- openpyxl: 3.1.2+
- Pillow: 10.0.0+
- Python: 3.11+

**參考資源**

- [openpyxl 官方文件](https://openpyxl.readthedocs.io/)
- [Pillow 影像處理指南](https://pillow.readthedocs.io/)
- [Excel OOXML 規格](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/)
