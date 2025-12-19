# Excel 圖片嵌入範例使用指南

本目錄包含 Python openpyxl 嵌入圖片到 Excel 的完整範例程式碼。

## 目錄結構

```
examples/
├── excel_image_examples.py    # 主要範例程式碼
├── requirements.txt           # Python 套件依賴
└── README.md                  # 本檔案
```

## 快速開始

### 1. 安裝依賴套件

```bash
# 使用 pip 安裝
pip install -r requirements.txt

# 或使用最小依賴（僅核心功能）
pip install openpyxl>=3.1.2 Pillow>=10.0.0
```

### 2. 執行範例程式

```bash
# 執行所有範例與效能測試
python excel_image_examples.py
```

執行後會在 `output/` 目錄產生以下檔案：

- `example_1_basic.xlsx` - 基本使用範例（10 筆項目）
- `example_2_large_dataset.xlsx` - 大量資料範例（200 筆項目）
- `example_3_mixed_images.xlsx` - 混合有無圖片範例（20 筆項目）
- `example_4_real_world.xlsx` - 真實場景模擬（30 筆項目）
- `benchmark_*.xlsx` - 效能測試輸出檔案

### 3. 在您的專案中使用

將範例程式碼中的類別複製到您的專案：

```python
from excel_image_examples import FairmontQuotationGenerator, BOQItem
from PIL import Image as PILImage

# 準備資料
items = [
    BOQItem(
        item_no="A-001",
        description="辦公桌",
        photo=PILImage.open('desk.jpg'),  # 您的圖片
        dimension="1800W x 800D x 750H mm",
        qty=5,
        uom="張",
        location="1F 辦公室",
        materials_specs="E1 防火板 25mm"
    )
]

# 生成報價單
generator = FairmontQuotationGenerator()
generator.add_items_batch(items)
generator.save('my_quotation.xlsx')
```

## 範例說明

### 範例 1：基本使用 (`example_1_basic_usage`)

展示基本的報價單生成流程：
- 生成 10 筆測試資料
- 包含圖片嵌入
- 標準惠而蒙格式

**適用場景**：小型報價單、快速驗證功能

### 範例 2：大量資料處理 (`example_2_large_dataset`)

展示批次處理大量項目：
- 生成 200 筆測試資料
- 批次處理（每 50 筆一批）
- 記憶體優化

**適用場景**：大型專案報價單、效能要求高

### 範例 3：混合圖片 (`example_3_mixed_images`)

展示處理有無圖片的混合情況：
- 70% 項目有圖片
- 30% 項目無圖片
- 自動處理缺失圖片

**適用場景**：PDF 解析後部分項目缺圖

### 範例 4：真實場景模擬 (`example_4_real_world_simulation`)

模擬從 PDF 提取資料的真實情況：
- 隨機圖片尺寸（100-400 像素）
- 隨機資料完整性（模擬解析遺漏）
- 80% 圖片覆蓋率

**適用場景**：整合 PDF 解析功能

## 效能測試

程式會自動執行以下效能測試：

1. **小型報價單 (10 項目，有圖片)**
2. **小型報價單 (10 項目，無圖片)** - 對照測試
3. **中型報價單 (50 項目，有圖片)**
4. **大型報價單 (100 項目，有圖片)**

測試指標包括：
- 執行時間（秒）
- 峰值記憶體使用（MB）
- 處理速度（項目/秒）

### 預期效能基準

根據測試環境（Intel i5, 16GB RAM）：

| 項目數 | 執行時間 | 峰值記憶體 | 處理速度 |
|--------|---------|-----------|---------|
| 10 筆  | 0.5-1s  | 50-80 MB  | 10-20 項/秒 |
| 50 筆  | 2-4s    | 100-150 MB | 12-25 項/秒 |
| 100 筆 | 4-8s    | 150-250 MB | 12-25 項/秒 |
| 200 筆 | 8-16s   | 250-400 MB | 12-25 項/秒 |

**注意**：實際效能取決於圖片大小、系統硬體等因素。

## 常見問題

### Q1: 圖片太大導致 Excel 檔案過大

**解決方案**：調整圖片最大尺寸

```python
# 修改 FairmontQuotationGenerator 類別中的設定
IMAGE_MAX_WIDTH = 100   # 降低到 100 像素
IMAGE_MAX_HEIGHT = 100
```

### Q2: 處理大量圖片時記憶體不足

**解決方案**：使用批次處理

```python
batch_size = 50  # 每批處理 50 筆
for i in range(0, len(items), batch_size):
    batch = items[i:i + batch_size]
    generator.add_items_batch(batch, start_row=2 + i)

    # 強制垃圾回收
    import gc
    gc.collect()
```

### Q3: 某些圖片格式無法嵌入

**解決方案**：使用格式轉換工具

```python
from excel_image_examples import convert_image_to_png

# 自動轉換為 PNG
img = convert_image_to_png('image.webp')  # 支援任意格式
```

### Q4: 圖片在 Excel 中未對齊儲存格

**檢查**：
1. 確認列高已設定：`ROW_HEIGHT_WITH_IMAGE = 90`
2. 確認欄寬已設定：`COLUMN_WIDTHS[3] = 20`（Photo 欄）
3. 確認圖片已調整大小：`IMAGE_MAX_WIDTH = 120`

### Q5: 如何從 PDF 提取圖片？

**參考文件**：查看 `docs/openpyxl-image-embedding-guide.md` 第 3.3 節

```python
import fitz  # PyMuPDF
from PIL import Image as PILImage
from io import BytesIO

def extract_images_from_pdf(pdf_path: str):
    pdf_document = fitz.open(pdf_path)
    images = []

    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]

            pil_img = PILImage.open(BytesIO(image_bytes))
            images.append(pil_img)

    return images
```

## 進階使用

### 自訂樣式

修改 `FairmontQuotationGenerator._setup_styles()` 方法：

```python
# 修改標題列顏色
header_style.fill = PatternFill(
    start_color='FF0000',  # 紅色
    end_color='FF0000',
    fill_type='solid'
)

# 修改字型
header_style.font = Font(
    name='Microsoft JhengHei',  # 微軟正黑體
    size=14,
    bold=True
)
```

### 新增自訂欄位

```python
# 在 COLUMNS 列表中新增欄位
COLUMNS = [
    'Item No.',
    'Description',
    'Photo',
    'Dimension',
    'Qty',
    'UOM',
    'Location',
    'Materials Used/Specs',
    'Unit Price',      # 新增欄位
    'Total Price'      # 新增欄位
]

# 調整欄位索引
COL_UNIT_PRICE = 9
COL_TOTAL_PRICE = 10

# 設定欄寬
COLUMN_WIDTHS[9] = 12
COLUMN_WIDTHS[10] = 12
```

### 多工作表報價單

```python
# 建立多個工作表
generator1 = FairmontQuotationGenerator()
generator1.ws.title = "家具報價"
generator1.add_items_batch(furniture_items)

# 新增第二個工作表
ws2 = generator1.wb.create_sheet("物料報價")
generator2 = FairmontQuotationGenerator()
generator2.ws = ws2
generator2.add_items_batch(material_items)

# 儲存包含兩個工作表的檔案
generator1.save('multi_sheet_quotation.xlsx')
```

## 整合到專案

### 建議目錄結構

```
your_project/
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── excel_generator.py  # 複製 FairmontQuotationGenerator
│   │   │   ├── pdf_parser.py       # PDF 解析服務
│   │   │   └── image_extractor.py  # 圖片提取服務
│   │   └── models/
│   │       └── boq_item.py         # 複製 BOQItem 資料模型
│   └── tests/
│       └── test_excel_generator.py # 單元測試
└── requirements.txt
```

### 測試建議

```python
# tests/test_excel_generator.py
import pytest
from app.services.excel_generator import FairmontQuotationGenerator
from app.models.boq_item import BOQItem

def test_generate_quotation_with_images():
    """測試生成含圖片的報價單"""
    items = [...]  # 測試資料
    generator = FairmontQuotationGenerator()
    generator.add_items_batch(items)
    output_file = generator.save('test_output.xlsx')

    assert Path(output_file).exists()
    assert Path(output_file).stat().st_size > 0

def test_handle_missing_images():
    """測試處理缺失圖片"""
    items = [BOQItem(..., photo=None)]  # 無圖片
    generator = FairmontQuotationGenerator()
    generator.add_item(items[0], row=2)

    # 驗證儲存格顯示「[無圖片]」
    assert generator.ws.cell(row=2, column=3).value == "[無圖片]"
```

## 參考資源

- **完整文件**：`docs/openpyxl-image-embedding-guide.md`
- **專案規格**：`specs/001-furniture-quotation-system/spec.md`
- **實作計畫**：`specs/001-furniture-quotation-system/plan.md`
- **openpyxl 官方文件**：https://openpyxl.readthedocs.io/
- **Pillow 文件**：https://pillow.readthedocs.io/

## 授權

本範例程式碼為 Fairmont Quotation System 專案的一部分。

---

**建立日期**：2025-12-19
**維護者**：Furniture Quotation System Team
**Python 版本**：3.11+
**openpyxl 版本**：3.1.2+
