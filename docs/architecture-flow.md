# 系統架構與 Skills 配置流程圖

## 整體架構概覽

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Skills 配置層 (YAML)                               │
├─────────────────────┬─────────────────────┬─────────────────────────────────┤
│  skills/vendors/    │  skills/output-     │  skills/core/                   │
│                     │  formats/           │                                 │
│  ┌───────────────┐  │  ┌───────────────┐  │  ┌───────────────┐              │
│  │ habitus.yaml  │  │  │ fairmont.yaml │  │  │ merge-rules   │              │
│  │ (供應商 A)    │  │  │ (惠而蒙格式)  │  │  │ .yaml         │              │
│  └───────────────┘  │  └───────────────┘  │  └───────────────┘              │
│  ┌───────────────┐  │  ┌───────────────┐  │                                 │
│  │ vendor-b.yaml │  │  │ company-b.yaml│  │  可新增其他                     │
│  │ (供應商 B)    │  │  │ (其他公司格式)│  │  合併規則                       │
│  └───────────────┘  │  └───────────────┘  │                                 │
└─────────────────────┴─────────────────────┴─────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SkillLoaderService                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ load_vendor("habitus")      → VendorSkill                            │   │
│  │ load_output_format("fairmont") → OutputFormatSkill                   │   │
│  │ load_merge_rules("merge-rules") → MergeRulesSkill                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 處理流程與 Skill 使用

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              使用者上傳 PDF                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  1. 文件角色偵測                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ DocumentRoleDetector                                                   │  │
│  │                                                                        │  │
│  │ 使用: MergeRulesSkill.role_detection                                   │  │
│  │ ├─ quantity_summary.filename_keywords: ["qty", "overall", ...]        │  │
│  │ └─ detail_spec.filename_keywords: ["casegoods", "fabric", ...]        │  │
│  │                                                                        │  │
│  │ 輸出: 文件角色 (quantity_summary / detail_specification)               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────────────┐
│  2a. 明細規格表解析              │   │  2b. 數量總表解析                        │
│  ┌───────────────────────────┐  │   │  ┌─────────────────────────────────────┐ │
│  │ PDFParserService          │  │   │  │ QuantityParserService               │ │
│  │                           │  │   │  │                                     │ │
│  │ 使用: VendorSkill         │  │   │  │ 使用: VendorSkill                   │ │
│  │ ├─ prompts.parse_         │  │   │  │ └─ prompts.parse_quantity_summary   │ │
│  │ │  specification          │  │   │  │    .user_template                   │ │
│  │ │  .user_template         │  │   │  │                                     │ │
│  │ ├─ field_extraction       │  │   │  │ 輸出: QuantitySummaryItem[]         │ │
│  │ │  (dimension, location)  │  │   │  │ ├─ item_no                          │ │
│  │ └─ document_types         │  │   │  │ └─ total_qty                        │ │
│  │                           │  │   │  └─────────────────────────────────────┘ │
│  │ 輸出: BOQItem[]           │  │   └─────────────────────────────────────────┘
│  └───────────────────────────┘  │                     │
└─────────────────────────────────┘                     │
                    │                                   │
                    ▼                                   │
┌─────────────────────────────────┐                     │
│  3. 圖片匹配                     │                     │
│  ┌───────────────────────────┐  │                     │
│  │ DeterministicImageMatcher │  │                     │
│  │                           │  │                     │
│  │ 使用: VendorSkill         │  │                     │
│  │ ├─ image_extraction       │  │                     │
│  │ │  .page_offset           │  │                     │
│  │ │  .by_document_type      │  │                     │
│  │ └─ image_extraction       │  │                     │
│  │    .exclusions            │  │                     │
│  │    (排除 logo, 色票等)    │  │                     │
│  │                           │  │                     │
│  │ 輸出: BOQItem + 圖片      │  │                     │
│  └───────────────────────────┘  │                     │
└─────────────────────────────────┘                     │
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  4. 跨表合併                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ MergeService                                                           │  │
│  │                                                                        │  │
│  │ 使用: MergeRulesSkill                                                  │  │
│  │ ├─ field_merge.strategies (欄位合併策略)                               │  │
│  │ ├─ quantity_merge.priority (數量來源優先順序)                          │  │
│  │ ├─ item_no_normalization.steps (Item No. 正規化)                       │  │
│  │ └─ constraints (限制: 最多 1 個數量總表)                               │  │
│  │                                                                        │  │
│  │ 輸出: 合併後的 BOQItem[] (含數量、已驗證標記)                          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  5. Excel 產出                                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ ExcelGeneratorService                                                  │  │
│  │                                                                        │  │
│  │ 使用: OutputFormatSkill (fairmont.yaml)                                │  │
│  │ ├─ company (公司名稱、地址、Logo)                                      │  │
│  │ ├─ layout (版面配置、列位置)                                           │  │
│  │ ├─ columns[] (15 欄定義)                                               │  │
│  │ │  ├─ header, field, width, alignment                                 │  │
│  │ │  └─ image_config (Photo 欄)                                         │  │
│  │ ├─ styles (標題列樣式、資料列樣式)                                     │  │
│  │ ├─ header_fields[] (表頭欄位: Project Name, RFQ#, Date...)            │  │
│  │ └─ terms (條款與備註)                                                  │  │
│  │                                                                        │  │
│  │ 輸出: Excel 檔案 (.xlsx)                                               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 新增供應商配置

```
新增供應商 "vendor-b":

1. 建立 skills/vendors/vendor-b.yaml
   ┌────────────────────────────────────────────────────────────┐
   │ vendor:                                                    │
   │   name: "Vendor B Design"                                  │
   │   identifier: "vendor-b"                                   │
   │                                                            │
   │ document_types:                                            │
   │   furniture_specification:                                 │
   │     filename_patterns: ["Furniture", "Case"]               │
   │   fabric_specification:                                    │
   │     filename_patterns: ["Textile", "Material"]             │
   │                                                            │
   │ image_extraction:                                          │
   │   page_offset:                                             │
   │     default: 2  # 不同供應商可能有不同的頁面結構           │
   │   exclusions:                                              │
   │     - type: "logo"                                         │
   │       rules:                                               │
   │         contains_text: "VENDOR B"                          │
   │                                                            │
   │ prompts:                                                   │
   │   parse_specification:                                     │
   │     user_template: |                                       │
   │       # 針對 Vendor B PDF 格式的專用 Prompt                │
   │       請分析 PDF 內容...                                   │
   └────────────────────────────────────────────────────────────┘

2. 呼叫時指定 vendor_id:
   parser = get_pdf_parser(vendor_id="vendor-b")
```

## 新增輸出格式（公司表格）

```
新增公司 "company-b" 的 Excel 格式:

1. 建立 skills/output-formats/company-b.yaml
   ┌────────────────────────────────────────────────────────────┐
   │ format:                                                    │
   │   name: "Company B Quotation Format"                       │
   │   identifier: "company-b"                                  │
   │                                                            │
   │ company:                                                   │
   │   name: "Company B International"                          │
   │   logo_file: "docs/company-b-logo.png"                     │
   │                                                            │
   │ layout:                                                    │
   │   rows:                                                    │
   │     data_header: 10  # 不同公司可能有不同的起始列          │
   │     data_start: 11                                         │
   │                                                            │
   │ columns:  # 可以定義不同的欄位數量和順序                   │
   │   - header: "序號"                                         │
   │     field: "no"                                            │
   │   - header: "品項編號"                                     │
   │     field: "item_no"                                       │
   │   # ... 其他欄位                                           │
   │                                                            │
   │ styles:                                                    │
   │   header:                                                  │
   │     fill_color: "FF5722"  # 不同公司可能有不同的品牌色     │
   └────────────────────────────────────────────────────────────┘

2. 呼叫時指定 format_id:
   generator = ExcelGeneratorService(format_id="company-b")
```

## Skill 配置對照表

| 服務 | 使用的 Skill | 配置用途 |
|------|-------------|----------|
| `PDFParserService` | VendorSkill | Prompt 模板、欄位提取規則 |
| `QuantityParserService` | VendorSkill | 數量總表 Prompt 模板 |
| `DeterministicImageMatcher` | VendorSkill | 圖片頁面偏移、排除規則 |
| `DocumentRoleDetector` | MergeRulesSkill | 文件角色關鍵字 |
| `MergeService` | MergeRulesSkill | 合併策略、欄位優先順序 |
| `ExcelGeneratorService` | OutputFormatSkill | 欄位定義、樣式、公司資訊 |

## 擴展性設計

```
                    ┌─────────────────────────────────────┐
                    │         SkillLoaderService          │
                    │  (統一載入、快取、驗證)              │
                    └─────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   VendorSkill       │   │  OutputFormatSkill  │   │   MergeRulesSkill   │
│                     │   │                     │   │                     │
│ • Prompt 模板       │   │ • 公司資訊          │   │ • 角色偵測規則      │
│ • 欄位提取規則      │   │ • 欄位定義          │   │ • 合併策略          │
│ • 圖片配置          │   │ • 樣式設定          │   │ • 正規化規則        │
│ • 文件類型定義      │   │ • 表頭/條款         │   │ • 限制條件          │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
          │                           │                           │
          ▼                           ▼                           ▼
   可新增多個供應商            可新增多個輸出格式           可自訂合併規則
   (habitus, vendor-b, ...)    (fairmont, company-b, ...)   (不同專案需求)
```

## 目前已配置

### 供應商 (vendors/)
- **habitus.yaml** - HABITUS Design Group
  - 家具明細表、面料明細表、數量總表解析
  - 圖片頁面偏移: furniture=1, fabric=1, quantity=0

### 輸出格式 (output-formats/)
- **fairmont.yaml** - 惠而蒙報價單格式
  - 15 欄定義 (NO., Item no., Description, Photo, ...)
  - 公司 Logo、表頭欄位、條款

### 合併規則 (core/)
- **merge-rules.yaml** - 跨表合併規則
  - 數量優先順序: quantity_summary > detail_spec
  - Item No. 正規化步驟
