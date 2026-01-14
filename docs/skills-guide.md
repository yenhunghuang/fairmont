# Skills 配置系統指南

## 概述

Skills 系統是本專案的核心配置機制，將業務邏輯從程式碼中抽離到 YAML 配置檔。這使得：

- 修改 Prompt 不需要改程式碼
- 新增供應商支援只需新增 YAML 檔案
- 非工程師也能調整部分業務規則

---

## 配置檔案結構

```
skills/
├── vendors/                    # 供應商配置
│   └── habitus.yaml           # Habitus 供應商（POC 預設）
├── output-formats/            # 輸出格式
│   └── fairmont.yaml          # 惠而蒙格式（POC 預設）
└── core/                      # 核心規則
    └── merge-rules.yaml       # 合併規則
```

---

## 供應商配置 (vendors/*.yaml)

### 完整結構

```yaml
# skills/vendors/habitus.yaml

id: habitus
name: Habitus Furniture
version: "1.0.0"

# === Prompt 模板 ===
prompts:
  parse_specification:
    system: |
      你是一個專業的家具規格表解析助手。
    user_template: |
      {categories_instruction}

      請從以下 PDF 內容提取家具項目：
      {pdf_content}

  parse_project_metadata:
    user_template: |
      從以下 PDF 內容提取專案名稱：
      {pdf_content}

  parse_quantity_summary:
    user_template: |
      從以下數量總表提取項目：
      {pdf_content}

# === 文件類型定義 ===
document_types:
  furniture_specification:
    patterns:
      - "FURNITURE SPECIFICATION"
      - "ITEM NO.:"
    priority: 1

  quantity_summary:
    patterns:
      - "QUANTITY SUMMARY"
      - "QTY SUMMARY"
    priority: 2

# === 圖片提取規則 ===
image_extraction:
  page_offset:
    default: 1
    by_document_type:
      furniture_specification: 1
      quantity_summary: 0

  exclusion_rules:
    - type: logo
      patterns:
        - "logo"
        - "watermark"
      max_size_kb: 50

    - type: color_swatch
      patterns:
        - "swatch"
        - "color"
      aspect_ratio_range: [0.8, 1.2]

# === 面料偵測 ===
fabric_detection:
  patterns:
    - "Vinyl to"
    - "Fabric to"
    - "Leather to"

# === 尺寸格式化 ===
dimension_formatting:
  furniture_keywords:
    - "mm"
    - "W x D x H"
    - "Dia."

  fabric_format: "{material}-{vendor}-{pattern}-{color}-{width}"
```

### 常見修改場景

#### 1. 修改解析 Prompt

```yaml
prompts:
  parse_specification:
    user_template: |
      # 在這裡修改 Prompt
      從以下 PDF 內容提取家具項目，注意：
      1. item_no 格式為 XXX-000
      2. 數量必須為正整數
      ...
```

#### 2. 新增文件類型識別

```yaml
document_types:
  # 新增類型
  material_schedule:
    patterns:
      - "MATERIAL SCHEDULE"
      - "MATERIALS"
    priority: 3
```

#### 3. 調整圖片排除規則

```yaml
image_extraction:
  exclusion_rules:
    # 新增規則
    - type: drawing
      patterns:
        - "CAD"
        - "drawing"
      min_size_kb: 500  # 大於 500KB 的工程圖
```

---

## 輸出格式配置 (output-formats/*.yaml)

### 完整結構

```yaml
# skills/output-formats/fairmont.yaml

id: fairmont
name: 惠而蒙報價單格式
version: "1.0.0"

# === 欄位定義 ===
columns:
  - key: no
    header: "NO."
    width: 5
    align: center

  - key: item_no
    header: "Item no."
    width: 15
    align: left

  - key: description
    header: "Description"
    width: 30
    wrap: true

  - key: photo
    header: "Photo"
    width: 20
    type: image
    max_height: 100

  - key: dimension
    header: "Dimension"
    width: 25

  - key: qty
    header: "Qty"
    width: 8
    align: right
    format: number

  - key: uom
    header: "UOM"
    width: 8
    align: center

  - key: unit_rate
    header: "Unit Rate"
    width: 12
    align: right
    editable: true  # 使用者填寫

  - key: amount
    header: "Amount"
    width: 12
    align: right
    formula: "=F{row}*H{row}"  # 數量 x 單價

  # ... 其他欄位

# === 樣式設定 ===
styles:
  header:
    font: "Arial"
    size: 11
    bold: true
    background: "#4472C4"
    color: "#FFFFFF"

  data:
    font: "Arial"
    size: 10
    border: thin

  alternate_row:
    background: "#F2F2F2"

# === 頁腳條款 ===
footer:
  terms:
    - "1. 報價有效期為 30 天"
    - "2. 付款條件：訂金 50%，出貨前 50%"
    - "3. 交貨期：確認訂單後 45 工作天"
```

### 常見修改場景

#### 1. 調整欄位寬度

```yaml
columns:
  - key: description
    width: 40  # 加寬
```

#### 2. 新增欄位

```yaml
columns:
  # 在適當位置插入
  - key: supplier
    header: "Supplier"
    width: 15
```

#### 3. 修改頁腳條款

```yaml
footer:
  terms:
    - "1. 新的條款內容..."
```

---

## 合併規則配置 (core/merge-rules.yaml)

### 完整結構

```yaml
# skills/core/merge-rules.yaml

id: merge-rules
version: "1.0.0"

# === 文件角色定義 ===
document_roles:
  detail_specification:
    keywords:
      - "FURNITURE SPECIFICATION"
      - "ITEM NO.:"
      - "SPECIFICATION SHEET"
    priority: 1

  quantity_summary:
    keywords:
      - "QUANTITY SUMMARY"
      - "QTY SUMMARY"
      - "數量總表"
    priority: 2

# === 欄位合併策略 ===
field_merge_strategies:
  default: fill_empty    # 預設：空值填補

  location:
    strategy: concatenate
    separator: ", "      # 多個位置用逗號分隔

  note:
    strategy: concatenate
    separator: "; "      # 多個備註用分號分隔

  qty:
    strategy: override   # 數量以數量總表為準
    source: quantity_summary

# === 面料跟隨規則 ===
fabric_ordering:
  enabled: true
  insert_after_furniture: true  # 面料插入到對應家具之後

# === 項目編號比對 ===
item_matching:
  normalize_patterns:
    - pattern: "([A-Z]{2,4})-?(\\d+)"
      replacement: "$1-$2"

  fuzzy_threshold: 0.9  # 模糊比對閾值
```

### 常見修改場景

#### 1. 調整合併策略

```yaml
field_merge_strategies:
  materials_specs:
    strategy: concatenate  # 改為串接而非覆蓋
    separator: "\n"
```

#### 2. 新增角色識別關鍵字

```yaml
document_roles:
  detail_specification:
    keywords:
      - "FURNITURE SPECIFICATION"
      - "新的關鍵字"
```

---

## 服務與配置對應表

| 服務 | 使用的配置 | 說明 |
|------|-----------|------|
| `PDFParserService` | `vendors/*.yaml` → `prompts` | 解析 Prompt 模板 |
| `QuantityParserService` | `vendors/*.yaml` → `prompts` | 數量總表 Prompt |
| `ExcelGeneratorService` | `output-formats/*.yaml` | 欄位、樣式、條款 |
| `MergeService` | `merge-rules.yaml` + `vendors/*.yaml` | 合併策略、面料偵測 |
| `DocumentRoleDetector` | `merge-rules.yaml` → `document_roles` | 角色識別關鍵字 |
| `ImageMatcher` | `vendors/*.yaml` → `image_extraction` | 圖片排除、頁面偏移 |
| `DimensionFormatter` | `vendors/*.yaml` → `dimension_formatting` | 尺寸格式化關鍵字 |

---

## 開發注意事項

### 1. 快取機制

**預設情況**：Skills 配置會被快取，修改後需重啟服務。

**開發時**：設定環境變數停用快取：

```bash
SKILLS_CACHE_ENABLED=false
```

### 2. 配置驗證

配置載入時會進行 Pydantic 驗證。如果 YAML 格式錯誤，會看到詳細錯誤訊息：

```
ValidationError: 1 validation error for VendorSkill
prompts.parse_specification.user_template
  field required (type=value_error.missing)
```

### 3. 預設值與 Fallback

如果配置項缺失，`SkillLoaderService` 會使用預設值：

```python
# skill_loader.py
def load_vendor_or_default(self, vendor_id: str) -> VendorSkill:
    try:
        return self.load_vendor(vendor_id)
    except SkillNotFoundError:
        return self._get_default_vendor_skill()
```

### 4. 新增供應商

1. 複製現有配置：
   ```bash
   cp skills/vendors/habitus.yaml skills/vendors/new-vendor.yaml
   ```

2. 修改 `id` 和內容

3. 在程式碼中使用：
   ```python
   parser = get_pdf_parser(vendor_id="new-vendor")
   ```

---

## 疑難排解

### Q: 配置修改後沒有生效？

1. 確認 `SKILLS_CACHE_ENABLED=false`
2. 或重啟後端服務
3. 檢查 YAML 語法是否正確

### Q: 出現 SkillNotFoundError？

1. 確認檔案路徑正確
2. 確認 YAML 中的 `id` 與檔名一致
3. 檢查 `skills/` 目錄是否在專案根目錄

### Q: Prompt 變數未替換？

確認使用正確的變數名稱（用 `{}` 包圍）：

```yaml
user_template: |
  {categories_instruction}  # 正確
  {{categories_instruction}}  # 錯誤（會被跳過）
```

---

## 範例：新增客戶專用格式

假設需要為新客戶「ABC 公司」建立專用輸出格式：

```yaml
# skills/output-formats/abc-company.yaml

id: abc-company
name: ABC 公司報價單格式
version: "1.0.0"

columns:
  # 根據客戶需求定義欄位
  - key: no
    header: "項次"
    width: 5

  - key: item_no
    header: "品號"
    width: 12

  # ... 其他欄位

footer:
  terms:
    - "ABC 公司專用條款 1"
    - "ABC 公司專用條款 2"
```

然後在程式碼中使用：

```python
generator = get_excel_generator(format_id="abc-company")
```
