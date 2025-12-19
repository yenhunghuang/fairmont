# openpyxl 圖片嵌入快速參考

快速查閱常用程式碼片段與關鍵設定。

## 基本操作

### 1. 嵌入圖片（檔案路徑）

```python
from openpyxl import Workbook
from openpyxl.drawing.image import Image

wb = Workbook()
ws = wb.active

img = Image('photo.jpg')
ws.add_image(img, 'C2')  # 嵌入到 C2 儲存格

wb.save('output.xlsx')
```

### 2. 嵌入圖片（記憶體 BytesIO）

```python
from openpyxl.drawing.image import Image
from PIL import Image as PILImage
from io import BytesIO

pil_img = PILImage.open('photo.jpg')

img_bytes = BytesIO()
pil_img.save(img_bytes, format='PNG')
img_bytes.seek(0)

img = Image(img_bytes)
ws.add_image(img, 'C2')
```

### 3. 調整圖片大小

```python
from PIL import Image as PILImage

pil_img = PILImage.open('large_photo.jpg')

# 保持長寬比縮放到 120x120 以內
original_width, original_height = pil_img.size
scale = min(120 / original_width, 120 / original_height)
new_size = (int(original_width * scale), int(original_height * scale))

resized_img = pil_img.resize(new_size, PILImage.Resampling.LANCZOS)

# 轉換為 openpyxl Image
img_bytes = BytesIO()
resized_img.save(img_bytes, format='PNG')
img_bytes.seek(0)
img = Image(img_bytes)

ws.add_image(img, 'C2')
```

## 儲存格設定

### 4. 設定欄寬與列高

```python
from openpyxl.utils import get_column_letter

# 設定欄寬（字元單位，1 單位 ≈ 7.5 像素）
ws.column_dimensions['C'].width = 20  # C 欄約 150 像素

# 或使用數字索引
col_letter = get_column_letter(3)  # 'C'
ws.column_dimensions[col_letter].width = 20

# 設定列高（點，1 點 = 1.33 像素）
ws.row_dimensions[2].height = 90  # 約 120 像素
```

### 5. 批次設定多欄寬度

```python
column_widths = {
    'A': 10,   # Item No.
    'B': 30,   # Description
    'C': 20,   # Photo
    'D': 15,   # Dimension
    'E': 8,    # Qty
    'F': 10,   # UOM
    'G': 20,   # Location
    'H': 35    # Materials/Specs
}

for col, width in column_widths.items():
    ws.column_dimensions[col].width = width
```

## 樣式設定

### 6. 建立標題列樣式

```python
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# 標題列樣式
header_cell = ws['A1']
header_cell.value = "Item No."
header_cell.font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
header_cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
header_cell.alignment = Alignment(horizontal='center', vertical='center')
header_cell.border = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)
```

### 7. 使用命名樣式（效能優化）

```python
from openpyxl.styles import NamedStyle, Font, Alignment

# 建立命名樣式（只建立一次）
header_style = NamedStyle(name="header")
header_style.font = Font(bold=True, size=12)
header_style.alignment = Alignment(horizontal='center', vertical='center')

wb.add_named_style(header_style)

# 應用到多個儲存格（高效）
for cell in ws[1]:  # 第一列所有儲存格
    cell.style = 'header'
```

### 8. 凍結窗格（固定標題列）

```python
# 凍結第一列（標題列）
ws.freeze_panes = 'A2'

# 凍結前兩列
ws.freeze_panes = 'A3'

# 凍結第一欄與第一列
ws.freeze_panes = 'B2'
```

## 圖片處理

### 9. 從 PDF 提取圖片

```python
import fitz  # PyMuPDF
from PIL import Image as PILImage
from io import BytesIO

pdf_document = fitz.open('document.pdf')
page = pdf_document[0]  # 第一頁
image_list = page.get_images(full=True)

for img_info in image_list:
    xref = img_info[0]
    base_image = pdf_document.extract_image(xref)
    image_bytes = base_image["image"]

    pil_img = PILImage.open(BytesIO(image_bytes))
    # 處理圖片...

pdf_document.close()
```

### 10. 轉換任意格式為 PNG

```python
from PIL import Image as PILImage
from io import BytesIO

def convert_to_png(image_path: str) -> BytesIO:
    """轉換任意圖片格式為 PNG BytesIO"""
    pil_img = PILImage.open(image_path)

    # 處理透明度
    if pil_img.mode in ('RGBA', 'LA', 'P'):
        background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
        if pil_img.mode == 'P':
            pil_img = pil_img.convert('RGBA')
        background.paste(pil_img, mask=pil_img.split()[-1])
        pil_img = background
    elif pil_img.mode != 'RGB':
        pil_img = pil_img.convert('RGB')

    img_bytes = BytesIO()
    pil_img.save(img_bytes, format='PNG', optimize=True)
    img_bytes.seek(0)

    return img_bytes
```

## 批次處理

### 11. 批次嵌入圖片

```python
image_files = ['img1.jpg', 'img2.jpg', 'img3.jpg']

for idx, img_file in enumerate(image_files):
    row = idx + 2  # 從第 2 列開始（第 1 列是標題）

    # 嵌入圖片到 C 欄
    img = Image(img_file)
    ws.add_image(img, f'C{row}')

    # 寫入其他資料
    ws[f'A{row}'] = f'Item-{idx+1}'
    ws[f'B{row}'] = f'Description {idx+1}'

    # 設定列高
    ws.row_dimensions[row].height = 90
```

### 12. 大量資料記憶體優化

```python
import gc

batch_size = 50
total_items = 200

for i in range(0, total_items, batch_size):
    # 處理一批資料
    for j in range(batch_size):
        if i + j >= total_items:
            break

        row = i + j + 2
        # ... 處理資料 ...

    # 每批次後進行垃圾回收
    gc.collect()
    print(f"已處理 {min(i + batch_size, total_items)}/{total_items}")
```

## 錯誤處理

### 13. 處理缺失圖片

```python
from pathlib import Path

def safe_add_image(ws, img_path: str, cell: str):
    """安全嵌入圖片，處理檔案不存在的情況"""
    if Path(img_path).exists():
        try:
            img = Image(img_path)
            ws.add_image(img, cell)
        except Exception as e:
            print(f"圖片嵌入失敗 ({img_path}): {e}")
            ws[cell] = "[圖片載入失敗]"
    else:
        ws[cell] = "[無圖片]"

# 使用範例
safe_add_image(ws, 'photo.jpg', 'C2')
```

### 14. 驗證圖片尺寸

```python
from PIL import Image as PILImage

def validate_image_size(img_path: str, max_size_mb: int = 5) -> bool:
    """驗證圖片檔案大小"""
    file_size_mb = Path(img_path).stat().st_size / (1024 * 1024)

    if file_size_mb > max_size_mb:
        print(f"警告：圖片過大 ({file_size_mb:.2f} MB)，建議壓縮")
        return False

    return True

def validate_image_dimensions(img_path: str, max_width: int = 4000, max_height: int = 4000) -> bool:
    """驗證圖片像素尺寸"""
    pil_img = PILImage.open(img_path)
    width, height = pil_img.size

    if width > max_width or height > max_height:
        print(f"警告：圖片解析度過高 ({width}x{height})，建議調整")
        return False

    return True
```

## 檔案儲存

### 15. 儲存並驗證

```python
from pathlib import Path

def save_excel(wb, output_path: str):
    """儲存 Excel 並驗證"""
    output_path = Path(output_path)

    # 確保目錄存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 儲存
    wb.save(output_path)

    # 驗證
    if output_path.exists():
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"檔案已儲存: {output_path} ({file_size_mb:.2f} MB)")
    else:
        raise IOError(f"儲存失敗: {output_path}")

# 使用範例
save_excel(wb, 'output/quotation.xlsx')
```

### 16. 壓縮檔案大小

```python
# openpyxl 預設使用 ZIP 壓縮，無需額外設定

# 優化技巧：
# 1. 使用 PNG 格式並啟用 optimize
img_bytes = BytesIO()
pil_img.save(img_bytes, format='PNG', optimize=True)

# 2. 壓縮 JPEG 品質（如果使用 JPEG）
pil_img.save(img_bytes, format='JPEG', quality=85, optimize=True)

# 3. 移除未使用的工作表
for sheet in wb.worksheets:
    if sheet.title == 'Sheet':  # 預設空白工作表
        wb.remove(sheet)
```

## 惠而蒙格式專用

### 17. 標準欄位設定

```python
# 惠而蒙格式 8 個標準欄位
COLUMNS = [
    'Item No.',           # A 欄，寬度 10
    'Description',        # B 欄，寬度 30
    'Photo',              # C 欄，寬度 20
    'Dimension',          # D 欄，寬度 15
    'Qty',                # E 欄，寬度 8
    'UOM',                # F 欄，寬度 10
    'Location',           # G 欄，寬度 20
    'Materials Used/Specs'  # H 欄，寬度 35
]

# 寫入標題
for col_idx, col_name in enumerate(COLUMNS, start=1):
    ws.cell(row=1, column=col_idx, value=col_name)
```

### 18. 圖片欄位標準尺寸

```python
# 惠而蒙格式推薦設定
IMAGE_MAX_WIDTH = 120   # 像素
IMAGE_MAX_HEIGHT = 120  # 像素
ROW_HEIGHT = 90         # 點（約 120 像素）
PHOTO_COL_WIDTH = 20    # 字元（約 150 像素）

# 設定 Photo 欄
ws.column_dimensions['C'].width = PHOTO_COL_WIDTH

# 設定含圖片的列高
for row in range(2, ws.max_row + 1):
    ws.row_dimensions[row].height = ROW_HEIGHT
```

## 效能基準

### 19. 簡易效能測試

```python
import time

start_time = time.time()

# 您的程式碼
generator = FairmontQuotationGenerator()
generator.add_items_batch(items)
generator.save('output.xlsx')

end_time = time.time()
print(f"執行時間: {end_time - start_time:.2f} 秒")
```

### 20. 記憶體監控

```python
import tracemalloc

tracemalloc.start()

# 您的程式碼
generator = FairmontQuotationGenerator()
generator.add_items_batch(items)

current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"目前記憶體: {current / 1024 / 1024:.2f} MB")
print(f"峰值記憶體: {peak / 1024 / 1024:.2f} MB")
```

## 常用單位轉換

```python
# Excel 單位轉換參考

# 欄寬（字元單位）
# 1 字元 ≈ 7.5 像素（字型 11pt Calibri）
column_width_chars = pixels / 7.5

# 列高（點）
# 1 點 = 1.33 像素
row_height_points = pixels / 1.33

# EMU（Excel Metric Units）
# 1 英吋 = 914400 EMU
# 1 像素 ≈ 9525 EMU（96 DPI）
emu = pixels * 9525
```

## 檔案大小估算

```python
# 粗略估算 Excel 檔案大小

# 基礎檔案：約 5-10 KB
# 每筆文字資料：約 0.1-0.5 KB
# 每張圖片（120x120 PNG）：約 10-30 KB

# 範例：100 筆項目，每筆含圖片
base_size = 10  # KB
text_size = 100 * 0.3  # 30 KB
image_size = 100 * 20  # 2000 KB (2 MB)
total_size = base_size + text_size + image_size  # 約 2.04 MB

print(f"預估檔案大小: {total_size / 1024:.2f} MB")
```

---

**參考完整文件**：`docs/openpyxl-image-embedding-guide.md`
**範例程式碼**：`examples/excel_image_examples.py`
